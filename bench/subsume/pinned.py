"""Pinned inputs for the faults derived cases miss (bench tooling).

    pinned.py <workspace root> <package dir> <src file>... --report r.json --harness h.ts
              [-n N] [--seed S] [-j N]

For a layout or routing module, `subsume` can leave hundreds of surviving
faults that reading alone cannot sort into equivalent or not. This plants
each survivor of a `subsume` report (the same sources, in the same order,
so its `#n` names the same fault) in a private mirror and runs N random
inputs through the package twice, as is and with the fault. A fault no
input tells apart is likely equivalent; for each other one, the first
input that tells it apart is shrunk line by line while it still does.
Then the fewest shrunk inputs that tell every such fault apart are kept,
each with the summary keys its faults change: a test pins those keys.

The harness is a family's own Bun script. Its directory is copied into the
mirror's package root as `.pinned/` (so a harness imports `../src/...`, the
planted copy, and its neighbours, such as a shared generator):
`gen <seed> <count>` prints a JSON list of inputs (generation must not use
the package's code); `eval` reads a JSON list of inputs on stdin and prints
a JSON list of flat summaries ({key: value}, or {"error": message} when an
input throws). An input whose summary is an error is never kept. A fault
whose run hangs or fails is listed apart, as `subsume` does. Prints one
JSON report. Every Bun run is capped as `subsume`'s are. Max, 2026-10-30: kept in `bench/` this time (the flowchart's
scripts were lost with a session scratchpad).
"""
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subsume  # noqa: E402

HARNESS_DIR = ".pinned"
EVAL_TIMEOUT = 120
CHUNK = 500  # inputs per eval run


def changed_keys(base: dict, other: dict) -> list[str]:
    """The summary keys whose values differ, an absent key counting as a change."""
    return sorted(key for key in base.keys() | other.keys() if base.get(key, None) != other.get(key, None)
                  or (key in base) != (key in other))


def shrink(lines: list[str], still_differs) -> list[str]:
    """Delete one line at a time, keeping each deletion the fault still shows on, until none does.

    `still_differs` takes a list of candidate inputs (each a list of lines)
    and returns the index of the first that still tells the fault apart, or
    None. The first line (the header) is never deleted.
    """
    while True:
        candidates = [lines[:i] + lines[i + 1:] for i in range(1, len(lines))]
        if not candidates:
            return lines
        hit = still_differs(candidates)
        if hit is None:
            return lines
        lines = candidates[hit]


def cover(tells: dict[str, set]) -> list[str]:
    """The fewest inputs (greedy) that together tell every fault apart; `tells` maps input -> faults.

    Ties go to the shorter input, then the earlier in sort order.
    """
    left = set().union(*tells.values()) if tells else set()
    chosen = []
    while left:
        best = max(sorted(tells, key=lambda s: (len(s), s)), key=lambda s: len(tells[s] & left))
        if not tells[best] & left:
            break
        chosen.append(best)
        left -= tells[best]
    return chosen


HARNESS_NAME = ""


def harness(copy: Path, *args, stdin=None):
    try:
        proc = subprocess.run(subsume.capped([subsume.BUN, f"{HARNESS_DIR}/{HARNESS_NAME}", *args]), cwd=copy, input=stdin, capture_output=True, text=True,
                              timeout=EVAL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def evaluate(copy: Path, inputs: list[str]):
    """Each input's summary by the package in `copy`, or None when a run hangs or fails."""
    out = []
    for start in range(0, len(inputs), CHUNK):
        part = harness(copy, "eval", stdin=json.dumps(inputs[start:start + CHUNK]))
        if part is None:
            return None
        out.extend(part)
    return out


def valid(summary: dict) -> bool:
    return "error" not in summary


def main():
    args = sys.argv[1:]

    def option(flag, default, cast=str):
        nonlocal args
        if flag not in args:
            return default
        i = args.index(flag)
        value = cast(args[i + 1])
        args = args[:i] + args[i + 2:]
        return value

    jobs = option("-j", 2, int)
    count = option("-n", 3000, int)
    seed = option("--seed", 1, int)
    report = json.loads(Path(option("--report", None)).read_text())
    harness_file = Path(option("--harness", None)).resolve()
    global HARNESS_NAME
    HARNESS_NAME = harness_file.name
    workspace, package, sources = Path(args[0]).resolve(), Path(args[1]).resolve(), args[2:]

    work = [(source, line, label, text) for source in sources
            for line, label, text in subsume.mutants((package / source).read_text())]
    wanted = [int(re.search(r"#(\d+)$", mid).group(1)) for mid in report["survivors"]]
    assert all(work[n][0] in mid for n, mid in zip(wanted, report["survivors"])), "report and sources disagree"

    scratch = Path(tempfile.mkdtemp(prefix="pinned-"))
    try:
        copies = []
        for n in range(jobs):
            (scratch / str(n)).mkdir()
            copy = subsume.mirror(workspace, package, scratch / str(n))
            shutil.copytree(harness_file.parent, copy / HARNESS_DIR)
            copies.append(copy)
        inputs = harness(copies[0], "gen", str(seed), str(count))
        base = evaluate(copies[0], inputs)
        assert base is not None, "the harness fails on the unplanted package"
        print(json.dumps(_run(work, wanted, report["survivors"], copies, inputs, base), indent=1))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run(work, wanted, names, copies, inputs, base):
    free = list(copies)

    def planted(copy, source, text, run):
        target = copy / source
        original = target.read_text()
        target.write_text(text)
        try:
            return run()
        finally:
            target.write_text(original)

    def one(n):
        source, _, _, text = work[n]
        copy = free.pop()
        try:
            faulty = planted(copy, source, text, lambda: evaluate(copy, inputs))
            if faulty is None:
                return n, "unattributed", None
            first = next((i for i, (b, f) in enumerate(zip(base, faulty)) if valid(b) and changed_keys(b, f)), None)
            if first is None:
                return n, "equivalent", None

            def still_differs(candidates):
                texts = ["\n".join(c) for c in candidates]
                good = evaluate(copy, texts)
                bad = planted(copy, source, text, lambda: evaluate(copy, texts))
                if good is None or bad is None:
                    return None
                return next((i for i, (b, f) in enumerate(zip(good, bad)) if valid(b) and changed_keys(b, f)), None)

            return n, "told", "\n".join(shrink(inputs[first].split("\n"), still_differs))
        finally:
            free.append(copy)

    equivalent, unattributed, shrunk = [], [], {}
    with cf.ThreadPoolExecutor(len(copies)) as pool:
        for n, verdict, small in pool.map(one, wanted):
            name = names[wanted.index(n)]
            if verdict == "equivalent":
                equivalent.append(name)
            elif verdict == "unattributed":
                unattributed.append(name)
            else:
                shrunk[name] = small

    # Which shrunk inputs tell which faults apart, and on which keys.
    candidates = sorted(set(shrunk.values()))
    good = evaluate(copies[0], candidates)
    tells, keys = {c: set() for c in candidates}, {}

    def matrix(name):
        n = wanted[names.index(name)]
        source, _, _, text = work[n]
        copy = free.pop()
        try:
            return name, planted(copy, source, text, lambda: evaluate(copy, candidates))
        finally:
            free.append(copy)

    with cf.ThreadPoolExecutor(len(copies)) as pool:
        for name, bad in pool.map(matrix, shrunk):
            for c, b, f in zip(candidates, good, bad or []):
                changed = changed_keys(b, f) if valid(b) else []
                if changed:
                    tells[c].add(name)
                    keys.setdefault(c, {})[name] = changed
    chosen = cover(tells)
    return {
        "survivors": len(names), "searched": len(inputs), "equivalent": equivalent, "unattributed": unattributed,
        "told": len(shrunk),
        "pinned": [{"input": c, "faults": sorted(tells[c]),
                    "keys": sorted(set().union(*keys[c].values())), "summary": dict(zip(candidates, good))[c]}
                   for c in chosen],
    }


if __name__ == "__main__":
    main()
