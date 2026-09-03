"""The navigation scorer (ADR-099 §4.5): what a reply names — and, at
v2, a defines path by unique suffix — plus the rescore script that
applies a scorer change to a stored run without touching it."""

import json
import sys
from pathlib import Path

import pytest

from hobbes.ttt.score import (
    SCORER_VERSION, classify_defines_failure, known_paths, norm_defines, path_tokens, score_reply, suffix_matches,
)

PATHS = {"go/internal/proxy/proxy.go", "go/internal/knowledge/knowledge.go", "go/cmd/hobbes-proxy/main.go",
         "go/cmd/hobbes-web/main.go", "pipeline/src/hobbes/cli.py"}
KNOWN = PATHS | {"go/internal/proxy/proxy.cappedBuffer", "hobbes.cli.main", "go/internal/proxy/proxy"}
TRUTH = "go/internal/proxy/proxy.go"


def defines(symbol: str, path: str) -> dict:
    return {"kind": "qa", "family": "defines", "symbol": symbol,
            "messages": [{"role": "user", "content": f"Which file defines `{symbol}`?"},
                         {"role": "assistant", "content": f"`{symbol}` is defined in `{path}` at lines 1–2 (function)."}]}


class TestPathTokens:
    def test_strips_markup_sha_and_line_suffixes(self):
        assert path_tokens("It is **proxy.go** (`proxy.go:393`), see ./knowledge.go@ebdf7a5.") == ["proxy.go", "knowledge.go"]

    def test_known_paths_are_the_path_shaped_members(self):
        assert known_paths(KNOWN) == PATHS | {"go/internal/proxy/proxy.cappedBuffer"}


class TestNormDefines:
    def test_full_path(self):
        assert norm_defines("in `go/internal/proxy/proxy.go`", TRUTH, PATHS)

    def test_unique_basename(self):
        assert norm_defines("The file is **proxy.go**.", TRUTH, PATHS)

    def test_partial_suffix(self):
        assert norm_defines("`proxy/proxy.go`", TRUTH, PATHS)

    def test_sha_and_line_suffixes(self):
        assert norm_defines("proxy.go@ebdf7a510eff", TRUTH, PATHS) and norm_defines("proxy.go:393", TRUTH, PATHS)

    def test_ambiguous_basename_identifies_neither(self):
        assert suffix_matches("main.go", PATHS) == ["go/cmd/hobbes-proxy/main.go", "go/cmd/hobbes-web/main.go"]
        assert not norm_defines("It is in main.go.", "go/cmd/hobbes-web/main.go", PATHS)

    def test_wrong_path_and_nothing(self):
        assert not norm_defines("knowledge.go", TRUTH, PATHS) and not norm_defines("no idea", TRUTH, PATHS)

    def test_score_reply_uses_it(self):
        rec = defines("go/internal/proxy/proxy.cappedBuffer", TRUTH)
        assert score_reply(rec, "**proxy.go**", KNOWN)["score"] == 1.0
        assert score_reply(rec, "**main.go**", KNOWN)["score"] == 0.0
        assert SCORER_VERSION == 2


class TestClassify:
    @pytest.mark.parametrize("reply, reason", [
        ("The file is `proxy.go`.", "right path, wrong format"),
        ("Defined in `go/internal/knowledge/knowledge.go`.", "wrong path"),
        ("`knowledge.go`", "wrong path"),
        ("I cannot find that symbol; it is not defined.", "refused"),
        ("The proxy package, line 393.", "no path named"),
    ])
    def test_reasons(self, reply, reason):
        rec = defines("go/internal/proxy/proxy.cappedBuffer", TRUTH)
        assert classify_defines_failure(rec, reply, KNOWN) == reason

    def test_ambiguous_needs_the_truth_among_the_matches(self):
        rec = defines("go/cmd/hobbes-web/main.main", "go/cmd/hobbes-web/main.go")
        assert classify_defines_failure(rec, "It lives in main.go.", KNOWN) == "ambiguous basename"


@pytest.fixture
def scripts_path():
    here = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(here))
    yield here
    sys.path.remove(str(here))


class TestRescore:
    def test_rebuilds_rows_from_the_corpus_and_never_overwrites(self, tmp_path, scripts_path):
        import ttt_rescore
        rec = defines("go/internal/proxy/proxy.cappedBuffer", TRUTH)
        (tmp_path / "eval.jsonl").write_text(json.dumps(rec) + "\n")
        old = {"model": "m", "context": "card", "items": "eval", "n": 2, "navigation_mean": 0.0,
               "families": {"defines": {"n": 2, "mean": 0.0}},
               "rows": [{"family": "defines", "symbol": rec["symbol"], "score": 0.0, "found": [], "missed": [TRUTH],
                         "extra": [], "refused": False, "reply": "**proxy.go**"},
                        {"family": "defines", "symbol": "ghost", "score": 0.0, "reply": "?"}]}
        records = ttt_rescore.records_by_key(tmp_path, "eval")
        assert set(records) == {("defines", rec["symbol"])}
        new = ttt_rescore.rescore(old, records, KNOWN, "old.json")
        assert new["scorer_version"] == SCORER_VERSION and new["rescored_from"] == "old.json"
        assert new["rows"][0]["score"] == 1.0 and new["rows"][1] == old["rows"][1] and new["rows_without_record"] == 1
        assert new["families"]["defines"]["mean"] == 0.5 and new["previous"]["families"]["defines"]["mean"] == 0.0
        assert new["model"] == "m" and new["context"] == "card"
        assert ttt_rescore.audit(old, records, KNOWN) == {"right path, wrong format": 1, "no record": 1}
        run_path = tmp_path / "run.json"; run_path.write_text(json.dumps(old))
        with pytest.raises(SystemExit):
            ttt_rescore.main([str(tmp_path), str(run_path), "--out", str(run_path)])
