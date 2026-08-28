"""The verification base (C-31): the pinned §3.8 table, stamped into
``graph.json`` and printed under the language list.

The one property that matters is agreement with the architecture: the
table in ``verification.py`` and the table in §3.8 are the same claim
in two places, and the test below reads the document so the two cannot
drift apart silently — extending a language's evidence means extending
both, in the same commit (§3.7 step 4).
"""

import re
from pathlib import Path

from hobbes import cli
from hobbes.extract import verification as v

ARCH = Path(__file__).parents[2] / "docs" / "hobbes-architecture.md"

#: §3.8's row label -> the artifact language names that row vouches for.
ROW_LANGUAGES = {
    "Python": ["python"],
    "TypeScript / JavaScript": ["typescript", "javascript"],
    "Go": ["go"],
    "Rust": ["rust"],
    "Terraform/HCL": ["hcl"],
}


def section_38_rows() -> dict[str, str]:
    text = ARCH.read_text()
    start = text.index("### 3.8 Coverage evidence")
    end = text.index("\n## ", start + 1)
    rows = {}
    for line in text[start:end].splitlines():
        m = re.match(r"\| \*\*(.+?)\*\* \| (.+?) \| ", line)
        if m:
            cell = re.sub(r"[*`]", "", m.group(2)).strip()
            rows[m.group(1)] = cell
    return rows


class TestTableAgreesWithArchitecture:
    def test_every_section_38_row_is_pinned_verbatim(self):
        rows = section_38_rows()
        assert set(rows) == set(ROW_LANGUAGES), rows
        for label, cell in rows.items():
            for lang in ROW_LANGUAGES[label]:
                assert v.VERIFICATION_BASE[lang]["on"] == cell, (lang, cell)

    def test_no_pinned_language_is_missing_from_the_table(self):
        covered = {l for langs in ROW_LANGUAGES.values() for l in langs}
        assert set(v.VERIFICATION_BASE) == covered

    def test_single_repo_rows_say_so(self):
        # Go left this list on 2026-08-25: the oracle lane graded it on a
        # second repo (dagger, 19 modules), so its row is multi-repo now.
        # Rust followed on the same day: the oracle lane's phase 2 graded
        # dagger's sdk/rust (O7). No single-repo language remains; the
        # depth adjective must still agree with the count for every row.
        for lang, row in v.VERIFICATION_BASE.items():
            assert (row["depth"] == "single-repo") == (row["repos"] == 1), lang


class TestVerificationBase:
    def test_rows_follow_artifact_language_order_and_carry_notes(self):
        base = v.verification_base(["rust", "python"])
        assert list(base) == ["rust", "python"]
        assert base["rust"]["note"] == (
            "verified on 3 repos: rust_proj (one small crate, re-earned under containment 2026-08-28); dagger — its sdk/rust workspace (O7); BurntSushi/memchr (2026-08-27/28)"
        )
        assert base["python"]["note"].startswith("verified on 8 repos:")

    def test_an_unknown_language_is_stated_as_unverified_not_dropped(self):
        base = v.verification_base(["cobol"])
        assert base["cobol"]["repos"] == 0
        assert base["cobol"]["depth"] == "unverified"
        assert base["cobol"]["note"] == "not verified on any repo"

    def test_summary_line_counts_per_language(self):
        base = v.verification_base(["rust", "python"])
        assert v.summary_line(base) == "rust 3 repos, python 8 repos"


class TestIngestSummary:
    def test_base_prints_under_the_language_list_and_spells_out_thin_rows(
        self, capsys
    ):
        cli._print_verification_base(v.verification_base(["rust", "python", "zig"]))
        out = capsys.readouterr().out
        assert "verification base: rust 3 repos, python 8 repos, zig 0 repos" in out
        assert "a sample, not the language (C-31" in out
        assert "    zig: not verified on any repo" in out
        # multi-repo rows are not spelled out — since 2026-08-25 that is
        # every language but a new one (rust joined them at O7)
        assert "    python:" not in out
        assert "    rust:" not in out

    def test_the_artifact_carries_the_base(self):
        from hobbes.extract import extract_repo

        doc = extract_repo(Path(__file__).parent / "fixtures" / "miniapp").graph
        assert list(doc["verification_base"]) == doc["languages"]
        assert doc["verification_base"]["python"]["repos"] == 8
