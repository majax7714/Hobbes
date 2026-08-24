"""The M6 exit property: graph verdicts agree with the emitted tool's.

``check: emit`` compiles a record to a CI tool, and the unified checker
still answers in-process wherever the graph can see the rule. Two
checkers, one rule — so wherever both exist they must agree, in both
directions, or one of them is lying. This suite runs **the real
lint-imports** over a generated config for the first time in the
project's history (deferred at M8 because no target toolchain was
installed; import-linter is a dev dependency since V2.M6).

The first real execution immediately found an emitter bug the
shape-only tests could not: the ``except`` cross-product emits ignore
pairs that never occur as imports, and import-linter treats an
unmatched ignore as an error by default — a clean repo exited 1. The
regression lives here (`test_unmatched_ignore_pairs_do_not_fail`).
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.invariants.compile import _emit_import_linter
from hobbes.invariants.schema import Invariant
from hobbes.invariants.verdict import FAIL, PASS, judge

pytestmark = pytest.mark.skipif(
    shutil.which("lint-imports") is None,
    reason="import-linter not installed (dev dependency)",
)


def record(**overrides) -> Invariant:
    fields = {
        "id": "I-1",
        "statement": "Only the parser touches json.",
        "scope": ".",
        "status": "confirmed",
        "check": "emit",
        "target": "import-linter",
        "rule": {
            "kind": "forbidden-import",
            "importers": ["*"],
            "except": ["agreementapp.parser"],
            # A stdlib target, so the fixture needs nothing installed —
            # and since ADR-038 the graph sees stdlib imports too.
            "imported": ["ext:json"],
        },
        "guarded_by": [],
        "source": "synthetic",
    }
    fields.update(overrides)
    return Invariant(**fields)


def write_fixture(root: Path, core_body: str) -> None:
    pkg = root / "agreementapp"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "parser.py").write_text(
        "import json\n\n\ndef parse(text):\n    return json.loads(text)\n"
    )
    (pkg / "core.py").write_text(textwrap.dedent(core_body))


def lint(root: Path, ini: str) -> int:
    config = root / "generated.ini"
    config.write_text(ini)
    # cwd puts agreementapp on the tool's path, the way a CI job would
    # run it from the repo root.
    proc = subprocess.run(
        ["lint-imports", "--config", str(config)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode


class TestAgreement:
    def test_a_violation_fails_both_judges(self, tmp_path):
        write_fixture(
            tmp_path,
            "import json\n\n\ndef run():\n    return json.dumps({})\n",
        )
        extraction = extract_repo(tmp_path)
        inv = record()

        verdict = judge(inv, extraction.graph)
        assert verdict.result == FAIL
        assert verdict.violations[0].importer == "agreementapp.core"

        assert lint(tmp_path, _emit_import_linter([inv], extraction.graph)) == 1

    def test_a_clean_tree_passes_both_judges(self, tmp_path):
        write_fixture(tmp_path, "def run():\n    return {}\n")
        extraction = extract_repo(tmp_path)
        inv = record()

        assert judge(inv, extraction.graph).result == PASS
        assert lint(tmp_path, _emit_import_linter([inv], extraction.graph)) == 0

    def test_unmatched_ignore_pairs_do_not_fail(self, tmp_path):
        # The bug the first real execution found: `except` entries that
        # never import the forbidden module emit ignore pairs with no
        # matching import, and import-linter's default treats that as an
        # error — a clean repo exited 1 while the graph said pass.
        write_fixture(tmp_path, "def run():\n    return {}\n")
        extraction = extract_repo(tmp_path)
        inv = record(
            rule={
                "kind": "forbidden-import",
                "importers": ["*"],
                # core never imports json in this variant, so its ignore
                # pair is unmatched by construction.
                "except": ["agreementapp.parser", "agreementapp.core"],
                "imported": ["ext:json"],
            }
        )

        assert judge(inv, extraction.graph).result == PASS
        ini = _emit_import_linter([inv], extraction.graph)
        assert "unmatched_ignore_imports_alerting = warn" in ini
        assert lint(tmp_path, ini) == 0


# --- C-19: the semgrep emitter, executed for real ------------------------

SEMGREP = shutil.which("semgrep") is not None
semgrep_only = pytest.mark.skipif(
    not SEMGREP, reason="semgrep not installed (dev dependency)"
)


def semgrep_record(**overrides) -> Invariant:
    fields = {
        "id": "I-5",
        "statement": "Nothing under core/ writes files directly.",
        "scope": ".",
        "status": "confirmed",
        "check": "emit",
        "target": "semgrep",
        "rule": {
            "kind": "pattern-absent",
            "languages": ["python"],
            "paths": ["core"],
            "patterns": ["$P.write_text(...)", "open($P, 'w')"],
        },
        "guarded_by": [],
        "source": "synthetic",
    }
    fields.update(overrides)
    return Invariant(**fields)


def run_semgrep(root: Path, config: str, target: str = ".") -> int:
    # The config lives outside *root*: for the dogfood-repo case, writing
    # it into the target would litter the real working tree.
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".yml", prefix="hobbes-semgrep-", delete=False
    ) as fh:
        fh.write(config)
        cfg = Path(fh.name)
    proc = subprocess.run(
        [
            "semgrep",
            "--config", str(cfg),
            "--error",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            target,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    cfg.unlink(missing_ok=True)
    # Exit 0 = clean, 1 = findings; anything else is semgrep itself
    # failing (a malformed generated config lands here, which is exactly
    # what this suite exists to catch).
    assert proc.returncode in (0, 1), proc.stderr[-500:]
    return proc.returncode


@semgrep_only
class TestSemgrepAgreement:
    """C-19's argument, replayed: lint-imports' first real run found an
    emitter bug the shape tests could not. The semgrep emitter gets the
    same treatment — a violating tree must fail, a clean one must pass,
    and the dogfood repo's own I-5 must hold against the real source."""

    def test_a_matching_pattern_fails_semgrep(self, tmp_path):
        core = tmp_path / "core"
        core.mkdir()
        (core / "writer.py").write_text(
            "def save(p, text):\n    p.write_text(text)\n"
        )
        inv = semgrep_record()
        from hobbes.invariants.compile import _emit_semgrep

        assert run_semgrep(tmp_path, _emit_semgrep([inv], {})) == 1

    def test_a_clean_tree_passes_semgrep(self, tmp_path):
        core = tmp_path / "core"
        core.mkdir()
        (core / "logic.py").write_text("def add(a, b):\n    return a + b\n")
        inv = semgrep_record()
        from hobbes.invariants.compile import _emit_semgrep

        assert run_semgrep(tmp_path, _emit_semgrep([inv], {})) == 0

    def test_an_excluded_path_may_do_what_the_rule_forbids(self, tmp_path):
        # I-5's real shape: schema.py is the validating writer and is
        # excluded. The exclusion must actually exclude.
        core = tmp_path / "core"
        core.mkdir()
        (core / "schema.py").write_text(
            "def persist(p, text):\n    p.write_text(text)\n"
        )
        inv = semgrep_record(
            rule={
                "kind": "pattern-absent",
                "languages": ["python"],
                "paths": ["core"],
                "exclude": ["core/schema.py"],
                "patterns": ["$P.write_text(...)"],
            }
        )
        from hobbes.invariants.compile import _emit_semgrep

        assert run_semgrep(tmp_path, _emit_semgrep([inv], {})) == 0

    def test_the_dogfood_i5_rule_holds_against_the_real_source(self):
        # The end-to-end that makes this suite mean something: the repo's
        # own I-5 record, compiled by the real emitter, run by the real
        # tool, over the real narrate/ package. A legitimate new write
        # path in narrate/ should fail here first — that is I-5 enforced,
        # not a flaky test.
        from hobbes.invariants.compile import _emit_semgrep
        from hobbes.invariants.schema import load_all

        repo = Path(__file__).parents[2]
        records = [
            r
            for r in load_all(repo)
            if r.check == "emit" and r.target == "semgrep"
        ]
        assert records, "the dogfood repo carries a semgrep-compiled record (I-5)"
        assert run_semgrep(repo, _emit_semgrep(records, {})) == 0
