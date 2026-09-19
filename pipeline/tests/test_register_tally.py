"""The constraint register has one tally, and it is the segment files'.

Every ``### C-n`` heading under ``docs/constraints/`` is one entry, and
its status is written on it: *lifted*, *superseded* or *folded* in the
heading, otherwise the first word of its **You find out** field. The
index's "Debt summary" table, its headline, and the copies in
``README.md``, ``CLAUDE.md`` and ``docs/session-handoff.md`` are held to
that read here — a copy had drifted at the 2026-09-16 and the 2026-09-18
reviews (the top-level review's docs item)."""
from __future__ import annotations

import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "constraints"

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen").split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n: int) -> str:
    """*n* (below 1,000) as the README spells it: ``one hundred and sixty-four``."""
    hundreds, rest = divmod(n, 100)
    if rest < 20:
        tail = ONES[rest] if rest or not hundreds else ""
    else:
        tail = TENS[rest // 10 - 2] + (f"-{ONES[rest % 10]}" if rest % 10 else "")
    head = f"{ONES[hundreds]} hundred" if hundreds else ""
    return " and ".join(part for part in (head, tail) if part)


def tally() -> Counter:
    """Each entry's status, read from the segment files."""
    counts: Counter = Counter()
    seen: set[str] = set()
    for segment in sorted(REGISTER.glob("*.md")):
        if segment.name in ("README.md", "HISTORY.md"):
            continue
        for part in re.split(r"(?m)^(?=### C-\d+)", segment.read_text()):
            heading = re.match(r"### (C-\d+)([^\n]*)", part)
            if heading is None:
                continue
            assert heading.group(1) not in seen, f"{heading.group(1)} is registered twice"
            seen.add(heading.group(1))
            title = heading.group(2).lower()
            closed = next((s for s in ("lifted", "superseded", "folded") if re.search(rf"\b{s}\b", title)), None)
            found = re.search(r"\*\*You find out:\*\*\s*\**\s*([A-Za-z/]+)", part)
            assert closed or found, f"{heading.group(1)} in {segment.name} states no surfacing status (P8)"
            counts[closed or found.group(1).lower()] += 1
    return counts


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_the_index_table_is_the_segment_files_tally():
    counts = tally()
    index = (REGISTER / "README.md").read_text()
    rows = {
        "surfaced": r"\| active — surfaced \| (\d+) \|",
        "partial": r"\| active — \*partial\* \| (\d+) \|",
        "unsurfaced": r"\| active — \*\*unsurfaced\*\* \(debt\) \| (\d+) \|",
        "n/a": r"\| active — n/a [^|]*\| (\d+) \|",
        "lifted": r"\| lifted \| (\d+) \|",
        "superseded": r"\| superseded \| (\d+) \|",
        "folded": r"\| folded \| (\d+) \|",
    }
    table = {status: int(re.search(pattern, index).group(1)) for status, pattern in rows.items()}
    assert table == dict(counts)
    active = sum(counts[s] for s in ("surfaced", "partial", "unsurfaced", "n/a"))
    headline = (
        f"**{words(sum(counts.values()))} entries: {words(active)} active, {words(counts['lifted'])} lifted, "
        f"{words(counts['superseded'])} superseded, {words(counts['folded'])} folded**"
    )
    assert headline.lower() in index.lower(), headline


def test_every_copy_of_the_tally_agrees():
    counts = tally()
    total = sum(counts.values())
    active = sum(counts[s] for s in ("surfaced", "partial", "unsurfaced", "n/a"))
    readme = (
        f"{words(total)} entries ({words(active)} active, {words(counts['lifted'])} lifted, "
        f"{words(counts['superseded'])} superseded, {words(counts['folded'])} folded)"
    )
    assert readme in flat((ROOT / "README.md").read_text()), readme
    digits = (
        f"{total} entries[;:] {active} active \\({counts['surfaced']} surfaced, {counts['partial']} partial, "
        f"{counts['unsurfaced']} unsurfaced\\b[^)]{{0,40}}?\\b{counts['n/a']} n/a\\), {counts['lifted']} lifted"
    )
    for copy in ("CLAUDE.md", "docs/session-handoff.md"):
        assert re.search(digits, flat((ROOT / copy).read_text())), f"{copy}: {digits}"


def test_words_spells_the_readmes_numbers():
    assert words(164) == "one hundred and sixty-four"
    assert words(119) == "one hundred and nineteen"
    assert words(28) == "twenty-eight" and words(100) == "one hundred" and words(6) == "six"
