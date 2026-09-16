"""The Calvin harness's session tracker (`docs/calvin/calvin-harness.md` §4).

The logs under `docs/calvin/sessions/S-*.md` are the record: this script
reads them and renders the count, the areas and the verdicts into one
table. It keeps nothing of its own — a stale table is a rendering bug,
not a data-entry one.

    python3 scripts/calvin_tracker.py render   # rewrite the README's tracker block
    python3 scripts/calvin_tracker.py check    # exit 1 if that block is stale

A line among the seven the harness writes (`**Task:**`, `**Doer:**`,
`**Egress:**`, `**Policy:**`, `**Branch:**`, `**Gate:**`, `**Verify:**`)
or the two the review block writes (`- gate:`, `- outcome:`) that does
not match one of the shapes seen in the fourteen sessions raises,
naming the file and the line — it never guesses and never drops a
session from the count.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = REPO_ROOT / "docs" / "calvin" / "sessions"
README = SESSIONS_DIR / "README.md"

BEGIN = "<!-- tracker:begin -->"
END = "<!-- tracker:end -->"

#: Max's validation target (`calvin-harness.md` §4, 2026-09-13).
TARGET_SESSIONS = 40

#: A file's area, by the first prefix it matches, checked in this order.
AREA_TABLE = [
    ("extraction", ("pipeline/src/hobbes/extract/", "tsextract/", "scip/")),
    # The knowledge tools' MCP schemas live in the proxy package (417f, the `path` alias), so that one file maps here,
    # ahead of the rest of `go/internal/proxy/` under the harness.
    ("knowledge tools", ("go/internal/knowledge/", "go/internal/proxy/knowledge.go")),
    ("oracle lane", ("bench/oracle/",)),
    ("harness and sandbox", (
        "go/internal/sandbox/", "go/internal/egress/", "go/internal/proxy/",
        "go/internal/recorder/", "go/internal/escalation/", "go/internal/policy/",
        "go/cmd/hobbes-session/", "go/cmd/hobbes-policy/", "go/cmd/hobbes-proxy/",
        "pipeline/src/hobbes/run/", "pipeline/src/hobbes/derive/",
        "pipeline/src/hobbes/bench/bench.box.policy", "sandbox/",
        "pipeline/scripts/calvin_tracker.py",
    )),
]

SESSION_ID_RE = re.compile(r"^S-(\d{4})(\d{2})(\d{2})T\d{6}Z-([0-9a-f]{4})$")

TASK_RE = re.compile(r"^- \*\*Task:\*\* .+\(brief `[^`]+`, task sha256 `[0-9a-f]+`\)$")

DOER_RE = re.compile(
    r"^- \*\*Doer:\*\* (?P<version>\S+) \(Claude Code\); model (?P<model>the default|\S+); "
    r"turns (?P<turns_num>—|\d+) of (?P<turns_den>\d+); "
    r"result `(?P<result>[^`]*)`(?: \*\*with an error\*\* \([^)]*\))?; "
    r"(?:reported cost \$(?P<cost>[\d.]+) \(the envelope's figure, on the subscription\); )?"
    r"wall (?P<wall>[\d.]+) s; session exit (?P<exit>-?\d+)$"
)

EGRESS_RE = re.compile(
    r"^- \*\*Egress:\*\* allow .+?; opened `[^`]+`×\d+(?:, `[^`]+`×\d+)*; "
    r"refused (?P<refused>none|`[^`]+`×\d+(?:, `[^`]+`×\d+)*)$"
)
REFUSED_ITEM_RE = re.compile(r"×(\d+)")

POLICY_RE = re.compile(
    r"^- \*\*Policy:\*\* (?P<total>\d+) exec decision\(s\) — "
    r"(?:none|(?P<kinds>`[a-z]+`×\d+(?:, `[a-z]+`×\d+)*))"
    r"(?:; escalated: .+)?"
    # The sink's bracket around the flight stream (ADR-112, 0.2.14-beta):
    # `; records: stream opened→closed`, or a WARNING naming what is missing.
    r"(?:; records: .+)?$"
)
KIND_ITEM_RE = re.compile(r"`([a-z]+)`×(\d+)")

BRANCH_NONE_RE = re.compile(r"^- \*\*Branch:\*\* none harvested — the session left no commit$")
BRANCH_RE = re.compile(r"^- \*\*Branch:\*\* `[^`]+`, \d+ commit\(s\); files: (?P<files>.+)$")
FILE_RE = re.compile(r"`([^`]+)`")

# The gate's and the grounder's version numbers are READ, never pinned.
# They were literals (`gate v2, grounder v3`) until 2026-09-16, when
# 0.2.28-beta moved the grounder to v4 for C-91 and the first session run
# at v4 (`S-20260916T153010Z-8170`) could not be parsed at all — the
# tracker refusing the harness's own current output. Every fixture in
# test_calvin_tracker.py held the same two literals, so the drift test
# could not see it either: a rule-version bump is a routine event, and
# nothing here may depend on its value.
GATE_RE = re.compile(
    r"^- \*\*Gate:\*\* \*\*(?P<verdict>clear|blocked)\*\* at `[0-9a-f]+` "
    r"\(gate v\d+, grounder v\d+, record `[0-9a-f]+`\)(?: — blocking: [\w, -]+)?; unknown \d+; "
    r"map over \d+ file\(s\), [\d.]+% of their lines uncaptured; partition checked$"
)

VERIFY_RE = re.compile(
    r"^- \*\*Verify:\*\* (?:empty|(?P<word>[A-Za-z][\w-]*); tests \d+, regressions \d+; "
    r"\{[^}]*\}(?:; build \{[^}]*\})?)$"
)

REVIEW_GATE_RE = re.compile(r"^- gate: (?P<word>[\w/-]+)")
REVIEW_OUTCOME_RE = re.compile(r"^- outcome: (?P<word>[A-Za-z][\w-]*)")

REQUIRED_LINES = ("task", "doer", "egress", "policy", "branch", "gate", "verify", "review_gate", "outcome")


def _is_test_path(path: str) -> bool:
    """A test file by its name or place: `*_test.go`, anything under a `tests/` directory, or a `test_*` file."""
    return path.endswith("_test.go") or path.startswith("tests/") or "/tests/" in path or Path(path).name.startswith("test_")


def area_for_files(files: list[str]) -> str:
    """The area(s) a session's branch touches: every `AREA_TABLE` category a file's prefix matches, joined `", "` in table order; `"—"` if none does.

    The code a session changed decides its area, so its test files count only when it changed nothing else (417f's
    `go/internal/proxy/mcp_test.go` tests the exec tools as well as the knowledge tools it changed)."""
    code = [f for f in files if not _is_test_path(f)]
    matched = set()
    for f in code or files:
        for name, prefixes in AREA_TABLE:
            if any(f.startswith(p) for p in prefixes):
                matched.add(name)
                break
    ordered = [name for name, _ in AREA_TABLE if name in matched]
    return ", ".join(ordered) if ordered else "—"


def parse_session(path: Path) -> dict:
    """One session log's harness record and review block, as a row of raw fields.

    A line starting one of the seven harness fields or the review's `gate`/`outcome`
    that fails its known shape raises `ValueError` naming *path* and the line number;
    a session missing one of those fields raises too. Never guesses, never drops one.
    """
    m = SESSION_ID_RE.match(path.stem)
    if not m:
        raise ValueError(f"{path}: not a session log filename")
    year, month, day, suffix = m.groups()
    rec: dict = {"id": path.stem, "suffix": suffix, "date": f"{year}-{month}-{day}"}
    seen: set[str] = set()

    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.rstrip()
        if line.startswith("- **Task:**"):
            if not TASK_RE.match(line):
                raise ValueError(f"{path}:{lineno}: cannot parse the Task line: {line!r}")
            seen.add("task")
        elif line.startswith("- **Doer:**"):
            dm = DOER_RE.match(line)
            if not dm:
                raise ValueError(f"{path}:{lineno}: cannot parse the Doer line: {line!r}")
            rec["turns_num"] = None if dm.group("turns_num") == "—" else int(dm.group("turns_num"))
            rec["turns_den"] = int(dm.group("turns_den"))
            rec["cost"] = float(dm.group("cost")) if dm.group("cost") else None
            rec["wall"] = float(dm.group("wall"))
            seen.add("doer")
        elif line.startswith("- **Egress:**"):
            em = EGRESS_RE.match(line)
            if not em:
                raise ValueError(f"{path}:{lineno}: cannot parse the Egress line: {line!r}")
            refused = em.group("refused")
            rec["egress_refused"] = 0 if refused == "none" else sum(int(n) for n in REFUSED_ITEM_RE.findall(refused))
            seen.add("egress")
        elif line.startswith("- **Policy:**"):
            pm = POLICY_RE.match(line)
            if not pm:
                raise ValueError(f"{path}:{lineno}: cannot parse the Policy line: {line!r}")
            kinds = dict(KIND_ITEM_RE.findall(pm.group("kinds") or ""))
            rec["policy_escalate"] = int(kinds.get("escalate", 0))
            rec["policy_deny"] = int(kinds.get("deny", 0))
            seen.add("policy")
        elif line.startswith("- **Branch:**"):
            if BRANCH_NONE_RE.match(line):
                rec["branch_files"] = []
            else:
                bm = BRANCH_RE.match(line)
                if not bm:
                    raise ValueError(f"{path}:{lineno}: cannot parse the Branch line: {line!r}")
                rec["branch_files"] = FILE_RE.findall(bm.group("files"))
            seen.add("branch")
        elif line.startswith("- **Gate:**"):
            gm = GATE_RE.match(line)
            if not gm:
                raise ValueError(f"{path}:{lineno}: cannot parse the Gate line: {line!r}")
            rec["gate"] = gm.group("verdict")
            seen.add("gate")
        elif line.startswith("- **Verify:**"):
            vm = VERIFY_RE.match(line)
            if not vm:
                raise ValueError(f"{path}:{lineno}: cannot parse the Verify line: {line!r}")
            rec["verify"] = vm.group("word") or "empty"
            seen.add("verify")
        elif line.startswith("- gate:"):
            rgm = REVIEW_GATE_RE.match(line)
            if not rgm:
                raise ValueError(f"{path}:{lineno}: cannot parse the review's gate line: {line!r}")
            rec["review_gate"] = rgm.group("word")
            seen.add("review_gate")
        elif line.startswith("- outcome:"):
            rom = REVIEW_OUTCOME_RE.match(line)
            if not rom:
                raise ValueError(f"{path}:{lineno}: cannot parse the review's outcome line: {line!r}")
            rec["outcome"] = rom.group("word")
            seen.add("outcome")

    missing = [f for f in REQUIRED_LINES if f not in seen]
    if missing:
        raise ValueError(f"{path}: missing line(s) for {', '.join(missing)}")

    rec["turns"] = "—" if rec["turns_num"] is None else f"{rec['turns_num']}/{rec['turns_den']}"
    rec["area"] = area_for_files(rec["branch_files"])
    return rec


def load_sessions(sessions_dir: Path = SESSIONS_DIR) -> list[dict]:
    """Every `S-*.md` session log under *sessions_dir*, parsed, in name (so chronological) order."""
    return [parse_session(p) for p in sorted(sessions_dir.glob("S-*.md"))]


def format_cost(cost: float | None) -> str:
    """`$X.XX`, or `—` when the session reported no cost at all."""
    return "—" if cost is None else f"${cost:.2f}"


def format_wall(seconds: float) -> str:
    """`N s` under 120 s, else `N min`."""
    return f"{round(seconds)} s" if seconds < 120 else f"{round(seconds / 60)} min"


def render_row(i: int, rec: dict) -> str:
    """One markdown table row for session *rec*, numbered *i*."""
    return (
        f"| {i} | [{rec['suffix']}]({rec['id']}.md) | {rec['date']} | {rec['area']} | "
        f"{rec['turns']} | {format_wall(rec['wall'])} | {format_cost(rec['cost'])} | "
        f"{rec['gate']} | {rec['verify']} | {rec['review_gate']} | {rec['outcome']} |"
    )


def distinct_areas(records: list[dict]) -> list[str]:
    """The distinct areas across *records* that have a mapped file, in `AREA_TABLE` order."""
    present = {a for rec in records for a in rec["area"].split(", ") if a != "—"}
    return [name for name, _ in AREA_TABLE if name in present]


def render_table(records: list[dict]) -> str:
    """The tracker block's markdown: the header, one row per session, then the totals lines."""
    lines = [
        "| # | session | date | area | turns | wall | cost | gate | verify | review | outcome |",
        "|---|---------|------|------|-------|------|------|------|--------|--------|---------|",
    ]
    lines.extend(render_row(i, rec) for i, rec in enumerate(records, start=1))

    n = len(records)
    areas = distinct_areas(records)
    false_blocks = sum(1 for r in records if r["review_gate"] == "false-block")
    missed = sum(1 for r in records if r["review_gate"] == "missed")
    egress_refused = sum(r["egress_refused"] for r in records)
    policy_escalate = sum(r["policy_escalate"] for r in records)
    policy_deny = sum(r["policy_deny"] for r in records)
    costed = [r["cost"] for r in records if r["cost"] is not None]
    turns_total = sum(r["turns_num"] for r in records if r["turns_num"] is not None)
    wall_min = round(sum(r["wall"] for r in records) / 60)

    lines.append("")
    lines.append(
        f"{n} of {TARGET_SESSIONS} sessions · areas: {', '.join(areas)} ({len(areas)}; at least 3) · "
        f"false blocks {false_blocks} · missed {missed}"
    )
    lines.append(
        f"refusals: egress {egress_refused}, policy escalations {policy_escalate}, "
        f"denies {policy_deny} (each read in its session's notes, §4)"
    )
    lines.append(
        f"reported cost ${sum(costed):.2f} over {len(costed)} of {n} sessions "
        f"(the envelope's figure, on the subscription) · turns {turns_total} · wall {wall_min} min"
    )
    lines.append(
        "This block is rendered by `pipeline/scripts/calvin_tracker.py render` from the logs "
        "and is not edited by hand."
    )
    return "\n".join(lines)


def current_block(text: str) -> str:
    """The text strictly between the tracker markers in *text*."""
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    return text[start:end].strip("\n")


def replace_block(text: str, new_block: str) -> str:
    """*text* with the tracker markers' contents replaced by *new_block*."""
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    return text[:start] + "\n\n" + new_block + "\n\n" + text[end:]


def cmd_render(_args: argparse.Namespace) -> int:
    """Rewrite the README's tracker block from the session logs."""
    records = load_sessions()
    README.write_text(replace_block(README.read_text(), render_table(records)))
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """Exit 1, naming `render`, if the README's tracker block is stale; 0 if it matches a fresh render."""
    records = load_sessions()
    fresh = render_table(records)
    if current_block(README.read_text()) != fresh:
        print(f"{README} is stale — run `pipeline/scripts/calvin_tracker.py render`")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """The `render` / `check` command line; returns the exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render", help="rewrite the README's tracker block from the logs")
    sub.add_parser("check", help="exit 1 if the tracker block is stale")
    args = parser.parse_args(argv)
    return cmd_render(args) if args.cmd == "render" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
