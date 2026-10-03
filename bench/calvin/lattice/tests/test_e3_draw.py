"""`bench/calvin/e3-draw/draw.py` as it ran: E3's pool, the GitHub search union.

The script runs at import time, so it is imported here with `gh` and `time.sleep` stubbed, in a scratch
working directory, and its `pool.json` is read back. `query` is then called directly for its two exits:
a rate limit it waits out, and any other failure, which stops the draw.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

E3_DRAW = Path(__file__).resolve().parents[2] / "e3-draw"


def gh_stub(pages, calls):
    """`subprocess.run` for `gh api`: each query's pages in order, keyed by the query's keyword."""

    def run(argv, capture_output, text):
        calls.append(argv)
        q = next(a for a in argv if a.startswith("q="))[2:]
        page = int(next(a for a in argv if a.startswith("page="))[5:])
        reply = pages(q, page)
        if isinstance(reply, subprocess.CompletedProcess):
            return reply
        return subprocess.CompletedProcess(argv, 0, json.dumps(reply), "")

    return run


def item(name):
    return {"full_name": name, "fork": False, "archived": False, "default_branch": "main", "size": 1,
            "stargazers_count": 20, "owner": {"login": name.split("/")[0]}, "license": {"spdx_id": "MIT"},
            "language": "C"}


@pytest.fixture
def drawn(monkeypatch, tmp_path):
    """Import `draw.py` afresh, which runs the draw, and return the `gh` calls it made."""
    calls = []

    def pages(q, page):
        keyword, licence = q.split()[0], q.split("license:")[1].split()[0]
        if keyword == "simd" and licence == "mit":  # two pages, one repo per page
            return {"total_count": 2, "items": [item(f"a/simd-{page}")]}
        # every other query finds one shared repo, so the union holds three
        return {"total_count": 1, "items": [item("b/shared")]}

    monkeypatch.setattr(subprocess, "run", gh_stub(pages, calls))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(E3_DRAW))
    monkeypatch.delitem(sys.modules, "draw", raising=False)
    import draw  # noqa: F401 — importing it is running it

    return calls


def test_the_draw_unions_every_keyword_and_licence_query(drawn, tmp_path):
    calls = drawn
    pool = json.loads((tmp_path / "pool.json").read_text())
    assert len(pool["queries"]) == 7 * 10  # seven keywords, ten licences
    assert len(calls) == 7 * 10 + 1  # simd/mit took two pages
    assert pool["union"] == 3 and sorted(pool["order"]) == ["a/simd-1", "a/simd-2", "b/shared"]
    # the order is the seeded shuffle, and each repo's row follows it
    assert [r["full_name"] for r in pool["repos"]] == pool["order"]
    assert pool["repos"][pool["order"].index("b/shared")]["spdx"] == "MIT"
    first = pool["queries"][0]
    assert first == {"q": "simd in:name,description,topics,readme language:C license:mit stars:>=20",
                     "total_count": 2, "returned": 2, "truncated": False}


def test_a_rate_limit_is_waited_out_and_any_other_failure_stops_the_draw(drawn, monkeypatch):
    import draw

    replies = [subprocess.CompletedProcess([], 1, "", "API rate limit exceeded"),
               {"total_count": 0, "items": []}]
    slept = []
    monkeypatch.setattr(subprocess, "run", gh_stub(lambda q, p: replies.pop(0), []))
    monkeypatch.setattr(time, "sleep", slept.append)
    assert draw.query("simd", 1) == {"total_count": 0, "items": []}
    assert slept == [65]

    monkeypatch.setattr(subprocess, "run", gh_stub(lambda q, p: subprocess.CompletedProcess([], 1, "", "boom"), []))
    with pytest.raises(SystemExit, match="query failed: simd p1"):
        draw.query("simd", 1)
