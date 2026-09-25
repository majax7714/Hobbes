"""Cell age: a small repository with a known history, walked for the name's date and the body's.

The repository the test builds has three commits on one kernel file: the first writes the cell, the
second rewrites its body, the third touches only a comment above it. So the name is as old as the file
and the body is as old as the second commit, and the walk has to tell those apart.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lattice import ages as ages_module
from lattice.cells import build

HEADER = """//
//  distance-avx2.c
//

#include "distance-avx2.h"

"""

FIRST = """float float32_distance_dot_avx2 (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;
    float total = 0.0f;
    for (int i = 0; i < n; ++i) total += a[i] * b[i];
    return total;
}
"""

SECOND = """float float32_distance_dot_avx2 (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;
    __m256 acc = _mm256_setzero_ps();
    return hsum256_ps(acc);
}
"""

DATES = ("2025-01-02T10:00:00+00:00", "2025-06-03T10:00:00+00:00", "2025-09-04T10:00:00+00:00")


def a_repo(root: Path) -> Path:
    """A git repository with the three commits above, at *root*. Returns it."""
    source = root / "src" / "distance-avx2.c"
    source.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "lattice@example.invalid")
    _git(root, "config", "user.name", "lattice tests")
    for date, text in (
        (DATES[0], HEADER + FIRST),
        (DATES[1], HEADER + SECOND),
        (DATES[2], HEADER.replace("//  distance-avx2.c", "//  distance-avx2.c — AVX2 kernels") + SECOND),
    ):
        source.write_text(text)
        _git(root, "add", "src/distance-avx2.c")
        _git(root, "commit", "-q", "-m", f"kernels at {date}", env={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    return root


def _git(root: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, env={**os.environ, **(env or {})}
    )


@pytest.fixture
def repo(tmp_path):
    return a_repo(tmp_path / "target")


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_the_name_is_as_old_as_the_file_and_the_body_as_old_as_its_rewrite(repo):
    rows = ages_module.ages(repo, "HEAD", build(repo))
    row = rows["avx2/float32/dot"]
    assert row["name_since"] == "2025-01-02"
    assert row["body_since"] == "2025-06-03"  # the third commit touched the file, not the body
    assert row["name"] == "float32_distance_dot_avx2"
    assert row["file"] == "src/distance-avx2.c"
    assert row["commits"] == 3
    assert row["reason"] is None


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_every_native_cell_gets_a_row_and_nothing_else_does(repo):
    rows = ages_module.ages(repo, "HEAD", build(repo))
    assert sorted(rows) == ["avx2/float32/dot"]


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_at_the_first_commit_the_body_is_that_commits_own(repo):
    first = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    rows = ages_module.ages(repo, first, build(repo))
    row = rows["avx2/float32/dot"]
    assert row["commits"] == 1
    assert (row["name_since"], row["body_since"]) == ("2025-01-02", "2025-01-02")


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_a_cell_the_ref_does_not_define_is_said_and_not_dated(repo):
    # the lattice's cells come from the working tree; a body only the working tree has is undated
    (repo / "src" / "distance-avx2.c").write_text(
        (repo / "src" / "distance-avx2.c").read_text() + "\nfloat float32_distance_l1_avx2 (const void *v1, const void *v2, int n) {\n    return 0.0f;\n}\n"
    )
    rows = ages_module.ages(repo, "HEAD", build(repo))
    row = rows["avx2/float32/l1"]
    assert (row["name_since"], row["body_since"]) == (None, None)
    assert row["reason"] == "float32_distance_l1_avx2 is not defined in src/distance-avx2.c at the ref"
    assert rows["avx2/float32/dot"]["body_since"] == "2025-06-03"  # the other cell still answers


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_identical_at_counts_the_bodies_the_tree_already_held(repo):
    rows = ages_module.ages(repo, "HEAD", build(repo))
    assert ages_module.identical_at(rows, "2025-03-31") == 0
    assert ages_module.identical_at(rows, "2025-06-30") == 1
    assert ages_module.identical_at(rows, "2025-12-31") == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="the age walk reads a real git history")
def test_the_rows_are_json_able_and_carry_no_absolute_path(repo):
    rows = ages_module.ages(repo, "HEAD", build(repo))
    dumped = json.dumps(rows, sort_keys=True)
    assert json.loads(dumped) == rows
    assert str(repo) not in dumped


def test_a_git_failure_is_its_own_error(tmp_path):
    with pytest.raises(ages_module.GitError):
        ages_module.ages(tmp_path, "HEAD", build(Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"))
