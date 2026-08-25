"""The verification base: how thin "supported" is, per language (C-31).

Architecture §3.8 is the sample behind every coverage claim (P11,
ADR-044): Python and TS/JS were hand-verified across several repos of
different shapes; **Go on this repo and 19 of dagger's modules**, both
compiler-graded by the oracle lane rather than hand-checked; **Rust on
one small repo**. A table in a document is not a surfacing (the register's
own rule), so this module pins that table and :func:`extract_repo`
stamps it into ``graph.json`` as ``verification_base`` — keyed by the
artifact's own language names — where the ingest summary, the surface's
language badges, and ``list_blind_spots`` read it in the moment a
language list is read as a capability list.

The table is **pinned, not derived**: there is nothing in a repo that
could compute how many other repos Hobbes was verified on. Extending a
language's claim means extending §3.8 *and this table* in the same
commit as the evidence (§3.7 step 4) — the test suite holds the two in
agreement by checking each row here against the architecture's table.
A language the table does not know is reported as verified on **zero**
repos, never omitted: an ingest that names a language it cannot vouch
for is the claim this module exists to qualify.
"""

from __future__ import annotations

#: §3.8, one row per artifact language name. ``repos`` counts repos with
#: hand-verified edges or lane agreement recorded in the table; ``on``
#: names them in the table's words; ``depth`` is the honest adjective.
VERIFICATION_BASE: dict[str, dict] = {
    "python": {
        "repos": 9,
        # This repo's zone is trace-graded since the oracle lane's phase 2
        # (ADR-089, O6, 2026-08-25): recall-against-executed, never precision.
        "on": "this repo (dogfood, continuous — trace-graded), private-repo-A, "
              "qwen-pathology; + six SWE-bench repos at span/declaration grain "
              "(astropy, django, scikit-learn, sphinx, sympy, xarray)",
        "depth": "multi-repo",
    },
    "typescript": {
        "repos": 3,
        "on": "kbet (real Vite+React app), private-repo-A, this repo's web/",
        "depth": "multi-repo",
    },
    "javascript": {
        "repos": 3,
        "on": "kbet (real Vite+React app), private-repo-A, this repo's web/",
        "depth": "multi-repo",
    },
    "go": {
        # Compiler-graded on both since the oracle lane (ADR-089, O2/O4,
        # 2026-08-25); the hand-check the row used to cite is retired.
        "repos": 2,
        "on": "this repo; dagger — 19 of its Go modules (O4)",
        "depth": "multi-repo",
    },
    "rust": {
        # Compiler-graded on both since the oracle lane's phase 2 (ADR-089,
        # O7, 2026-08-25); ADR-040's hand-check is superseded.
        "repos": 2,
        "on": "rust_proj (one small crate); dagger — its sdk/rust workspace (O7)",
        "depth": "multi-repo",
    },
    "hcl": {
        "repos": 2,
        "on": "private-repo-A, this repo",
        "depth": "multi-repo",
    },
}

#: A language the table has no row for: stated, never skipped.
UNVERIFIED = {"repos": 0, "on": "no verified repo", "depth": "unverified"}


def verification_base(languages: list[str]) -> dict[str, dict]:
    """The §3.8 row for each of *languages*, in the artifact's own order,
    with :data:`UNVERIFIED` for any name the table does not know. Every
    row also carries ``note``, the one-line form the consumers print."""
    out: dict[str, dict] = {}
    for lang in languages:
        row = dict(VERIFICATION_BASE.get(lang, UNVERIFIED))
        n = row["repos"]
        row["note"] = (
            f"verified on {n} repo{'' if n == 1 else 's'}: {row['on']}"
            if n
            else "not verified on any repo"
        )
        out[lang] = row
    return out


def summary_line(base: dict[str, dict]) -> str:
    """The ingest summary's one-line statement of the base — a sample,
    not the language (C-31), with the thinnest rows spelled out."""
    parts = []
    for lang, row in base.items():
        n = row["repos"]
        parts.append(f"{lang} {n} repo{'' if n == 1 else 's'}")
    return ", ".join(parts)
