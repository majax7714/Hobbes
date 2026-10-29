"""Mutation subsumption for a Bun workspace package's tests (bench tooling).

    subsume.py <workspace root> <package dir> <src file>... [--tests t...] [-j N]

Max's rule for our own tests of the opencode fork (2026-10-29): no test
that "only fails due to other tests failing". This makes it checkable.
It plants one small fault at a time in each named source file (operators,
±1, strings, regex anchors, a call replaced by its argument, a one-line
guard deleted), runs the package's tests, and records which cases fail.
A case is redundant when every fault it catches is caught by another kept
case. Faults no case catches are listed: read each, since many are
equivalent (they cannot change behavior) and the rest are gaps. A run
that hangs (a synchronous loop) is unattributable and listed apart.

The verdict is only as strong as the faults it can plant: a case that
guards something no operator touches looks redundant. Read a "redundant"
case before deleting it.

Workers mutate private mirrors of the workspace (the package copied, the
rest symlinked), never the real tree. Tests must import the package's
source relatively; a sibling package resolves to the real tree. Prints
one JSON report. Bun is `$BUN`, else the build's pinned copy.
"""
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

BUN = os.environ.get("BUN") or str(Path.home() / ".watterson/bun/1.4.2/bun")
CASE_TIMEOUT_MS = 5000  # a slowed test fails by itself
RUN_TIMEOUT = 60  # a hung run (a synchronous infinite loop) is unattributable

STRING = re.compile(r"""(["'])((?:\\.|(?!\1).)+)\1""")
REGEX = re.compile(r"""(?:(?<=[=(,:!&|?\[;])|(?<=[=(,:!&|?\[;] )|(?<=return ))/(?![/*\s])((?:\\.|\[(?:\\.|[^\]])*\]|[^/\\\n])+)/([dgimsuvy]*)""")

# (pattern, replacement): each match is one mutant. None = a computed replacement.
OPERATORS = [
    (r"===", "!=="), (r"!==", "==="),
    (r"(?<![<=!>])<=(?!=)", "<"), (r"(?<![=!>])>=(?!=)", ">"),
    (r"(?<![<=\w])< (?!=)", "<= "), (r"(?<![=>-]) > (?!=)", " >= "),
    (r"&&", "||"), (r"\|\|", "&&"),
    (r"(?<=\s)\+(?=\s)", "-"), (r"(?<=\s)-(?=\s)", "+"),
    (r"(?<=\s)\*(?=\s)", "/"), (r"(?<=\s)/(?=\s)", "*"), (r"(?<=\s)%(?=\s)", "*"),
    (r"\btrue\b", "false"), (r"\bfalse\b", "true"),
    (r"Math\.max\b", "Math.min"), (r"Math\.min\b", "Math.max"),
    (r"Math\.floor\b", "Math.ceil"), (r"Math\.ceil\b", "Math.floor"),
    (r"(?<![\w.$])(\d+)(?![\w.])", "int"),  # n -> n + 1
    (r"\.startsWith\(", ".endsWith("), (r"\.endsWith\(", ".startsWith("),
    (r"(?<![!=])!(?=[\w(])", ""),  # drop a negation
    (r"\bcontinue\b", "break"), (r"\bthrow\b", "void"),
    (r"(?<![\w$.\]])[A-Za-z_$][\w$.?]*(?= \?\? )", "undefined"),  # an option ignored
]
CALL = re.compile(r"(?<![\w$.])(Math\.min|Math\.max|[A-Za-z_$][\w$]*)\(")
KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "typeof", "function", "await", "yield", "void",
            "super", "import", "require", "get", "set", "async", "constructor"}


def call_args(line, open_at):
    """The top-level arguments of the call whose `(` ends at open_at, and the closing index; None when it spans lines."""
    depth, start, parts, quote, i = 0, open_at, [], None, open_at - 1
    while i + 1 < len(line):
        i += 1
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                parts.append(line[start:i])
                return ([] if parts == [""] else parts), i
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(line[start:i])
            start = i + 1
    return None


SKIP = re.compile(r"^\s*(//|\*|/\*|import\b|export (type|interface)\b|export \* |\} from )")


def literal_spans(line):
    """Spans of strings, template text, regex literals and a trailing comment."""
    spans, i, quote, start = [], 0, None, 0
    regexes = [(m.start(), m.end()) for m in REGEX.finditer(line)]
    while i < len(line):
        hit = next((r for r in regexes if r[0] == i), None)
        if quote is None and hit:
            spans.append((hit[0], hit[1] - 1))
            i = hit[1]
            continue
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                spans.append((start, i))
                quote = None
        elif ch in "\"'`":
            quote, start = ch, i
        elif line.startswith("//", i):
            spans.append((i, len(line)))
            break
        i += 1
    if quote:
        spans.append((start, len(line)))
    return spans, regexes


def mutants(text):
    lines = text.split("\n")

    def emit(number, label, line):
        return number + 1, label, "\n".join(lines[:number] + [line] + lines[number + 1:])

    for number, line in enumerate(lines):
        if SKIP.match(line):
            continue
        # A one-line guard deleted.
        if re.match(r"^\s*if \(.*\) (return|throw|continue|break)\b", line):
            yield emit(number, "drop guard", "")
        spans, regexes = literal_spans(line)
        inside = lambda pos: any(a <= pos <= b for a, b in spans)
        for pattern, replacement in OPERATORS:
            for match in re.finditer(pattern, line):
                if inside(match.start()):
                    continue
                new = str(int(match.group(1)) + 1) if replacement == "int" else replacement
                yield emit(number, f"{match.group(0)!r}->{new!r}", line[: match.start()] + new + line[match.end():])
        # A call replaced by its argument (a clamp or a conversion removed); a no-argument method call dropped.
        for match in CALL.finditer(line):
            name = match.group(1)
            if inside(match.start()) or name in KEYWORDS or re.search(r"(function|new|\.)\s*$", line[: match.start()]):
                continue
            args = call_args(line, match.end())
            if args is None:
                continue
            parts, close = args
            if name in ("Math.min", "Math.max") or len(parts) == 1:
                for part in parts:
                    yield emit(number, f"{name}(…)->{part.strip()[:20]!r}", line[: match.start()] + part.strip() + line[close + 1:])
        for match in re.finditer(r"(?<!\.)\.[A-Za-z_$][\w$]*\(\)", line):
            if not inside(match.start()):
                yield emit(number, f"drop {match.group(0)}", line[: match.start()] + line[match.end():])
        # A string literal's text changed (not a template: it may hold code).
        for match in STRING.finditer(line):
            if any(a <= match.start() <= b and a != match.start() for a, b in spans) or inside(match.start() - 1):
                continue
            if not any(a == match.start() for a, _ in spans):
                continue
            q, body = match.group(1), match.group(2)
            yield emit(number, f"string {match.group(0)[:30]!r}", line[: match.start()] + q + "~" + body + q + line[match.end():])
        # A regex literal that never matches, and one without each anchor.
        for start, end in regexes:
            body = line[start + 1: line.rindex("/", start, end)]
            yield emit(number, f"regex never {body[:20]!r}", line[: start + 1] + "(?!)" + line[start + 1:])
            if body.startswith("^"):
                yield emit(number, f"regex unanchored-start {body[:20]!r}", line[: start + 1] + line[start + 2:])
            if body.endswith("$") and not body.endswith("\\$"):
                close = line.rindex("/", start, end)
                yield emit(number, f"regex unanchored-end {body[:20]!r}", line[: close - 1] + line[close:])


def mirror(workspace, package, into):
    """A workspace copy: `package` copied, everything else symlinked."""
    rel = package.relative_to(workspace)
    for entry in workspace.iterdir():
        if entry.name != rel.parts[0]:
            os.symlink(entry, into / entry.name)
    parent = into / rel.parts[0]
    parent.mkdir()
    for entry in (workspace / rel.parts[0]).iterdir():
        if entry.name != rel.parts[1]:
            os.symlink(entry, parent / entry.name)
    shutil.copytree(package, into / rel, symlinks=True)
    return into / rel


def run(package, tests):
    with tempfile.NamedTemporaryFile(suffix=".xml") as out:
        try:
            proc = subprocess.run(
                [BUN, "test", "--timeout", str(CASE_TIMEOUT_MS), "--reporter=junit", f"--reporter-outfile={out.name}", *tests],
                cwd=package, capture_output=True, timeout=RUN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
        try:
            root = ET.parse(out.name).getroot()
        except ET.ParseError:
            return None, f"no report (exit {proc.returncode})"
    cases = {}
    for case in root.iter("testcase"):
        cases[f"{case.get('file')}::{case.get('name')}"] = case.find("failure") is not None or case.find("error") is not None
    return cases, "ok"


def redundant_cases(kills: dict[str, set]) -> tuple[list[dict], dict[str, set]]:
    """The redundant cases, and the kept ones with what each catches.

    Greedy, least-catching first: a case is dropped when the cases still
    kept catch every fault it does. Two cases that catch the same faults
    keep one (the later by name).
    """
    kept = dict(kills)
    redundant = []
    for name in sorted(kills, key=lambda n: (len(kills[n]), n)):
        others = set().union(*(k for n, k in kept.items() if n != name))
        if kills[name] <= others:
            also = sorted({n for n, k in kept.items() if n != name and k & kills[name]})
            redundant.append({"case": name, "caught": len(kills[name]), "also_caught_by": also})
            del kept[name]
    return redundant, kept


def main():
    args = sys.argv[1:]
    jobs = os.cpu_count() // 2
    if "-j" in args:
        i = args.index("-j")
        jobs = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    tests = []
    if "--tests" in args:
        i = args.index("--tests")
        args, tests = args[:i], args[i + 1:]
    workspace, package, sources = Path(args[0]).resolve(), Path(args[1]).resolve(), args[2:]
    baseline, status = run(package, tests)
    assert baseline is not None and not any(baseline.values()), f"baseline not green: {status}"
    work = [(source, line, label, text) for source in sources
            for line, label, text in mutants((package / source).read_text())]

    scratch = Path(tempfile.mkdtemp(prefix="subsume-"))
    copies = []
    for n in range(jobs):
        (scratch / str(n)).mkdir()
        copies.append(mirror(workspace, package, scratch / str(n)))
    free = list(copies)

    def one(item):
        source, line, label, text = item
        copy = free.pop()
        try:
            target = copy / source
            original = target.read_text()
            target.write_text(text)
            try:
                return item, run(copy, tests)
            finally:
                target.write_text(original)
        finally:
            free.append(copy)

    kills = {name: set() for name in baseline}
    survivors, unattributed = [], []
    with cf.ThreadPoolExecutor(jobs) as pool:
        for index, ((source, line, label, _), (cases, status)) in enumerate(pool.map(one, work)):
            # The index keeps two same-label faults on one line apart.
            mid = f"{source}:{line} {label} #{index}"
            if cases is None:
                unattributed.append((mid, status))
                continue
            failed = {name for name, bad in cases.items() if bad} | (set(baseline) - set(cases))
            if not failed:
                survivors.append(mid)
            for name in failed:
                kills.setdefault(name, set()).add(mid)
    shutil.rmtree(scratch)

    redundant, kept = redundant_cases(kills)
    print(json.dumps({
        "mutants": len(work), "caught": len(work) - len(survivors) - len(unattributed),
        "unattributed": unattributed, "redundant": redundant,
        "kept": {n: len(k) for n, k in kept.items()}, "survivors": survivors,
    }, indent=1))


if __name__ == "__main__":
    main()
