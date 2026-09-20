"""The verification base: how thin "supported" is, per language (C-31).

Architecture §3.8 is the sample behind every coverage claim (P11,
ADR-044): Python, TypeScript and JavaScript were verified across several
repos of different shapes (JavaScript's without their dependencies, C-165); **Go on this repo and 19 of dagger's modules**, both
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
        # private-repo-A and qwen-pathology retired from the base
        # 2026-08-25 (Max): too little weight to carry a row. click joined
        # 2026-08-27 (trace-graded); the counts follow the §3.8 rows.
        "repos": 8,
        # This repo's zone is trace-graded since the oracle lane's phase 2
        # (ADR-089, O6, 2026-08-25): recall-against-executed, never precision.
        "on": 'this repo (dogfood, continuous — trace-graded, twice); pallets/click (trace-graded); + six SWE-bench repos at span/declaration grain (astropy, django, scikit-learn, sphinx, sympy, xarray)',
        "depth": "multi-repo",
    },
    "typescript": {
        "repos": 4,
        "on": "kbet (real Vite+React app); ajv-validator/ajv, cheeriojs/cheerio (2026-08-27/28); this repo's web/ (lane agreement only)",
        "depth": "multi-repo",
    },
    "javascript": {
        # Until 0.2.53-beta this row copied TypeScript's; at 0.2.53-beta it
        # read 0 (C-165: no TS/JS cell was a JavaScript program). Graded
        # 2026-09-19 (ADR-140, oracle-grading.md §10.22): three JavaScript
        # repos, every graded edge confirmed on each; none had its
        # dependencies installed. A fourth, drawn for C-165 (§10.24,
        # 2026-09-20), was graded with its tree and again without: the
        # same rows, so the row says how many cells met one, no more. A
        # fifth (§10.27, 2026-09-20), drawn for size, read the same way:
        # 881 rows identical with its tree and without.
        "repos": 5,
        "on": "expressjs/express (CommonJS); preactjs/preact (ESM, JSDoc, JSX; its root zone); xmppjs/xmpp.js, cypress-io/github-action and Blueturboguy07/cue — drawn at random (2026-09-19/20); two of five graded with their dependency tree",
        "depth": "multi-repo",
    },
    "go": {
        # Compiler-graded on both since the oracle lane (ADR-089, O2/O4,
        # 2026-08-25); the hand-check the row used to cite is retired.
        "repos": 6,
        "on": 'this repo; dagger — 19 of its Go modules (O4); BurntSushi/toml, gorilla/mux, junegunn/fzf (2026-08-27/28); quic-go/quic-go — drawn at random, binary roots only (2026-09-02)',
        "depth": "multi-repo",
    },
    "rust": {
        # Compiler-graded on both since the oracle lane's phase 2 (ADR-089,
        # O7, 2026-08-25); ADR-040's hand-check is superseded.
        "repos": 3,
        "on": 'rust_proj (one small crate, re-earned under containment 2026-08-28); dagger — its sdk/rust workspace (O7); BurntSushi/memchr (2026-08-27/28)',
        "depth": "multi-repo",
    },
    "java": {
        # Compiler-graded from day one (ADR-096, O8): javac's own
        # resolution plus CHA, four repos in one session, two of them
        # drawn at random. No hand-checked edges — the fixture's are
        # hand-computed in the lane's test.
        "repos": 4,
        "on": 'jhy/jsoup (Maven library); spring-projects/spring-petclinic (Spring service); spring-data-elasticsearch and Legend-of-Dragoon-Modding/Severed-Chains — both drawn at random (2026-08-29)',
        "depth": "multi-repo",
    },
    "c": {
        # Compiler-graded against clang's own front end (ADR-110, O9,
        # 2026-09-12): a library chosen for shape and one repo drawn at
        # random. clang is also lane B's engine (scip-clang); the key
        # grades what Hobbes adds above the front end.
        "repos": 2,
        "on": "DaveGamble/cJSON (a library with its vendored Unity tests); sqliteai/sqlite-vector — drawn at random (2026-09-12)",
        "depth": "multi-repo",
    },
    "cpp": {
        # Compiler-graded against clang's own front end (ADR-113, O10,
        # 2026-09-15): a header-heavy library chosen for the `.h` claim
        # and one repo drawn at random, both regraded after ADR-113 §2's
        # third amendment (0.2.22-beta).
        "repos": 2,
        "on": "fmtlib/fmt (a header-heavy library with its bundled gtest and gmock); Taywee/args — drawn at random (2026-09-14)",
        "depth": "multi-repo",
    },
    "hcl": {
        "repos": 1,
        "on": "this repo only",
        "depth": "single-repo",
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
