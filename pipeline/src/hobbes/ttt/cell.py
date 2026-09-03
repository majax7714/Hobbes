"""The primary cell — HSR, RFE and ``manifest_ignore`` over derived units (ADR-099 §4.1–4.2; review item 9, 2026-09-03).

A **derived unit** is one unit of the change-spec ``hobbes plan``
writes for a hand-written proposal (design §2.3, source 1): the
proposal, the unit's interior paths, its guarding tests, and the
rendered manifest (:func:`hobbes.run.agents.render_context`). Four
arms run **one agent per unit** — *model + prompt* under P12, nothing
decomposes — on a fresh checkout at the base SHA:

| arm | model | prompt |
|---|---|---|
| A0 | base | the proposal |
| A1 | base | the proposal + the unit's manifest |
| A2 | adapter | the proposal |
| A3 | adapter | the proposal + the unit's manifest |

The agent is :mod:`hobbes.agent.loop` with **file tools only**
(``--no-bash``): it reads and edits, it cannot execute — so repo code
never runs, and the policy is the same in every arm (design §2.4). The
tool schemas ride the chat template and the loop reads the model's
calls from its text (``--tool-choice none``): the serve has no parser
for Olmo 3's ``<function_calls>`` syntax, and the first attempt died on
that 400 in every session (defect D-2 of the cell record). An
unaided arm's prompt is the same for every unit of a proposal, so it
runs once per proposal and its trajectory is scored against each unit
(``shared_run``), paired by unit like the rest.

**Scoring reads the transcript and the patch, never the wording.**
*HSR* counts the code-shaped references an agent emits — in fenced
code, in the content it writes or edits, and in backticks in prose —
and resolves each against the graph at the SHA: a symbol id, qualname
or name, a module id, a path, or an external import (``ext:``, logged
*unverifiable*); a name the agent's own edits define is excluded once
defined. *RFE* is Jaccard, precision and recall of the patch's files
against the unit's interior. *manifest_ignore* is set when an aided
arm's agent asserts that a file or test the manifest names does not
exist, or edits only outside the manifest's paths. Solve is
**recorded, not gated**, and in this pass means the patch is non-empty
and applies; the guarding tests are not run by anyone (defect D-1 of
the cell record). Computes; interprets nothing.
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ARMS = {"A0": (False, False), "A1": (False, True), "A2": (True, False), "A3": (True, True)}
#: What the agent is told, both arms; the manifest is the only variable.
TASK_HEAD = ("You are working in a checkout of {repo} at commit {sha12}. Implement the task below by "
             "changing files in this working tree. There is no shell in this session: read and edit "
             "files; you cannot run tests or commands. Do not create branches or commit. When the task "
             "is done, reply with a short summary of what you changed and what you could not verify.")
MANIFEST_CAP = 24_000
_KEYWORDS = {
    "self", "cls", "True", "False", "None", "true", "false", "null", "nil", "return", "import", "from", "def",
    "class", "func", "function", "const", "let", "var", "type", "struct", "interface", "package", "if", "else",
    "elif", "for", "while", "in", "not", "and", "or", "is", "with", "as", "try", "except", "finally", "raise",
    "yield", "await", "async", "lambda", "pass", "break", "continue", "del", "global", "nonlocal", "assert",
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple", "range", "enumerate", "zip",
    "map", "filter", "sorted", "open", "isinstance", "super", "object", "Exception", "ValueError", "TypeError",
    "KeyError", "RuntimeError", "Path", "Optional", "Any", "List", "Dict", "Set", "Tuple", "Union", "Callable",
    "string", "error", "err", "fmt", "os", "sys", "json", "re", "io", "err.Error", "fmt.Errorf", "fmt.Sprintf",
    "fmt.Println", "os.path", "os.path.join", "sys.exit", "json.dumps", "json.loads", "json.load", "json.dump",
    "re.compile", "re.match", "re.search", "re.sub", "re.findall", "subprocess", "subprocess.run", "time.time",
    "time", "typing", "dataclass", "dataclasses", "field", "pathlib", "pathlib.Path", "collections", "itertools",
    "functools", "contextlib", "logging", "unittest", "pytest", "pytest.fixture", "pytest.mark", "np", "pd",
    "console.log", "Promise", "Array", "Object", "String", "Number", "Boolean", "Error", "Map", "Set", "JSON",
    "JSON.parse", "JSON.stringify", "Math", "Date", "undefined", "this", "new", "export", "default", "extends",
    "implements", "public", "private", "static", "readonly", "void", "int64", "int32", "uint", "byte", "rune",
    "bytes", "strings", "errors", "context", "context.Context", "errors.New", "strings.Split", "strings.Join",
    "testing", "testing.T", "t.Fatalf", "t.Errorf", "t.Run", "t.Helper", "make", "append", "cap", "copy",
    "delete", "panic", "recover", "close", "chan", "go", "select", "switch", "case", "defer", "range",
}
_IDENT = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_TICK = re.compile(r"`([^`\n]+)`")
_DEFINES = re.compile(r"(?m)^\s*(?:def|class|func(?:\s*\([^)]*\))?|function|type|interface|const|let|var|export\s+(?:default\s+)?(?:function|class|const|let|var|type|interface))\s+([A-Za-z_][A-Za-z0-9_]*)")
_DENIAL = re.compile(r"\b(does not exist|doesn't exist|do not exist|don't exist|no such file|not found|is not present|is missing|cannot find|can't find|could not find|not defined|isn't defined|does not have|doesn't have)\b", re.I)


class CellError(RuntimeError):
    """A proposal set, a spec or a run that cannot yield a unit."""


@dataclass
class CellUnit:
    id: str
    commit: str
    proposal: str
    task: str
    unit: str
    paths: list[str]
    modules: list[str]
    guarding_tests: list[str]
    manifest: str
    seeds: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- units

def derive_units(repo_root: Path, proposals: dict[str, str], seeds_by_commit: dict[str, list[str]] | None = None,
                 derive=None, render=None, max_units: int | None = 4) -> tuple[list[CellUnit], list[dict]]:
    """One :class:`CellUnit` per non-deferred unit of ``hobbes plan`` over
    each proposal; *seeds_by_commit* gives the files the change starts
    from (the commit's files the base graph holds), lexical seeds
    otherwise. A proposal the planner refuses is recorded, not dropped.
    *derive* and *render* default to the pipeline's own."""
    from hobbes.derive.changespec import derive_plan, spec_to_dict
    from hobbes.run.agents import render_context
    derive = derive or (lambda proposal, seeds: spec_to_dict(derive_plan(repo_root, proposal, seeds=seeds or None,
                                                                          max_units=max_units)))
    render = render or render_context
    units: list[CellUnit] = []
    errors: list[dict] = []
    for commit in sorted(proposals):
        proposal = proposals[commit]
        seeds = list((seeds_by_commit or {}).get(commit, []))
        try:
            spec = derive(proposal, seeds)
        except Exception as exc:  # noqa: BLE001 — the planner's refusal is the record
            errors.append({"commit": commit, "error": f"{type(exc).__name__}: {exc}"})
            continue
        contexts = {c["unit"]: c for c in spec.get("contexts", [])}
        for u in spec.get("units", []):
            if u.get("deferred"):
                continue
            ctx = contexts.get(u["name"], {})
            paths = [m["path"] for m in ctx.get("modules", []) if m.get("path")]
            units.append(CellUnit(
                id=f"{commit[:12]}/{u['name']}", commit=commit, proposal=proposal, task=spec.get("task", ""),
                unit=u["name"], paths=paths, modules=[m["id"] for m in ctx.get("modules", [])],
                guarding_tests=list(ctx.get("guarding_tests", [])), manifest=render(spec, u["name"]),
                seeds=dict(spec.get("seeds", {})),
                notes=[] if paths else ["unit has no editable path"]))
    return units, errors


def write_units(units: list[CellUnit], path: Path, errors: list[dict] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [json.dumps(asdict(u), sort_keys=True, ensure_ascii=False) for u in units]
    if errors:
        rows.append(json.dumps({"_plan_errors": errors}, sort_keys=True))
    path.write_text("\n".join(rows) + "\n")


def read_units(path: Path) -> tuple[list[dict], list[dict]]:
    units, errors = [], []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            (errors.extend(row["_plan_errors"]) if "_plan_errors" in row else units.append(row))
    return units, errors


# ---------------------------------------------------------------- briefs

def brief(unit: dict, repo: str, sha12: str, aided: bool) -> str:
    """The agent's prompt: the head, the task, and — aided — the unit's manifest, capped and the cut stated."""
    parts = [TASK_HEAD.format(repo=repo, sha12=sha12), "", "## Task", unit["proposal"].strip()]
    if aided:
        manifest = unit["manifest"].strip()
        if len(manifest) > MANIFEST_CAP:
            manifest = manifest[:MANIFEST_CAP] + f"\n\n(derived context cut by {len(unit['manifest']) - MANIFEST_CAP:,} characters to fit — C-45)"
        parts += ["", f"## Derived context (Hobbes, graph @ {sha12}; the manifest of the unit this task was partitioned into)",
                  manifest]
    return "\n".join(parts)


# ---------------------------------------------------------------- running

def _git(cwd: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and proc.returncode:
        raise CellError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def checkout(source: Path, sha: str, dest: Path) -> Path:
    """A fresh working tree of *source* at *sha* under *dest* (a shared clone, no network)."""
    dest = Path(dest)
    if dest.exists():
        subprocess.run(["rm", "-rf", str(dest)], check=True)
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(source), str(dest)], check=True,
                   capture_output=True, text=True)
    _git(dest, "checkout", "-q", sha)
    return dest


def candidate_patch(workspace: Path) -> str:
    """The diff of everything the agent changed, staged and unstaged alike, ``.hobbes/`` excluded."""
    _git(workspace, "add", "-A", "--", ".", ":(exclude).hobbes")
    return _git(workspace, "diff", "--cached", "--no-color", "--", ".", ":(exclude).hobbes")


def run_agent(loop_path: Path, workspace: Path, prompt: str, base_url: str, model: str, *, max_turns: int = 30,
              max_tokens: int = 1536, temperature: float = 0.2, timeout: float = 1800.0,
              api_key_env: str = "HOBBES_LLM_API_KEY", thinking: str = "off", tool_choice: str = "none") -> dict:
    """One file-tools-only session of the owned loop; returns the envelope plus the transcript path and the patch."""
    hob = Path(workspace) / ".hobbes"
    hob.mkdir(exist_ok=True)
    (hob / "prompt.md").write_text(prompt)
    transcript = hob / "transcript.jsonl"
    cmd = [sys.executable, str(loop_path), "--base-url", base_url, "--model", model, "--api-key-env", api_key_env,
           "--prompt-file", str(hob / "prompt.md"), "--workdir", str(workspace), "--no-bash",
           "--max-turns", str(max_turns), "--max-tokens", str(max_tokens), f"--temperature={temperature}",
           f"--thinking={thinking}", "--tool-choice", tool_choice, "--transcript", str(transcript)]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, timeout=timeout)
        envelope = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {"is_error": True}
        error = "" if not envelope.get("is_error") else (proc.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        envelope, error = {"is_error": True, "num_turns": None}, f"timed out after {timeout:.0f}s"
    except (ValueError, IndexError) as exc:
        envelope, error = {"is_error": True}, f"no envelope: {exc}"
    patch = candidate_patch(workspace)
    return {"envelope": envelope, "error": error, "patch": patch, "transcript": str(transcript),
            "wall_s": round(time.monotonic() - started, 1), "model": model}


# ---------------------------------------------------------------- scoring

def graph_names(graph: dict) -> dict[str, set[str]]:
    """The name universes a reference resolves against, and the symbols
    with a semantic-tier edge (the others are declarations lane A parsed,
    their edges syntactic or none — counted in-graph, bucketed apart)."""
    ids, names, quals, modules, paths, ext = set(), set(), set(), set(), set(), set()
    for s in graph.get("symbols", []):
        ids.add(s["id"]); names.add(s.get("name", "")); quals.add(s.get("qualname", ""))
    for n in graph.get("nodes", []):
        if n.get("kind") == "external" or n["id"].startswith("ext:"):
            ext.add(n["id"][4:] if n["id"].startswith("ext:") else n["id"])
        else:
            modules.add(n["id"])
            if n.get("path"):
                paths.add(n["path"])
    semantic = set()
    for e in graph.get("symbol_edges", []):
        if e.get("tier", "syntactic") == "semantic":
            semantic.add(e.get("from")); semantic.add(e.get("to"))
    return {"ids": ids, "names": names - {""}, "quals": quals - {""}, "modules": modules, "paths": paths,
            "ext": ext, "semantic": semantic}


_URL = re.compile(r"https?://\S+|\b[\w.-]+\.(?:com|org|io|net|dev|md|txt|rst|json|yaml|yml|toml|lock|html)\b")
_DUNDER = re.compile(r"^__\w+__$")


def code_shaped(token: str) -> bool:
    """A token that reads as a reference to code rather than as a word:
    dotted, snake_case, camelCase or PascalCase with an interior
    capital, or carrying a digit. A capitalised word (``This``,
    ``Placeholder``), an all-caps word of up to five letters (``ADR``,
    ``TODO``), a lone underscore and a dunder (``__main__``) are not —
    the first cell run counted every one of them (2026-09-03)."""
    if len(token) < 2 or _DUNDER.match(token) or token.strip("_") == "":
        return False
    if "." in token or "_" in token or any(c.isdigit() for c in token):
        return True
    if token.isupper():
        return len(token) > 5
    return any(c.isupper() for c in token[1:])


def references(messages: list[dict]) -> tuple[list[str], set[str]]:
    """Every code-shaped reference the assistant emitted (fenced code,
    written/edited content, backticked prose), in order, and the names
    its own writes define."""
    refs: list[str] = []
    defined: set[str] = set()
    for m in messages:
        if m.get("role") != "assistant":
            continue
        code_blobs, prose = [], m.get("content") or ""
        for fence in _FENCE.findall(prose):
            code_blobs.append(fence)
        prose = _FENCE.sub(" ", prose)
        for call in m.get("tool_calls") or []:
            fn = call.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            for key in ("content", "new_text"):
                if isinstance(args.get(key), str):
                    code_blobs.append(args[key])
        for blob in code_blobs:
            blob = _URL.sub(" ", blob)
            defined.update(_DEFINES.findall(blob))
            refs += [t for t in _IDENT.findall(blob) if code_shaped(t) and t not in _KEYWORDS]
        for tick in _TICK.findall(_URL.sub(" ", prose)):
            tick = tick.strip().rstrip("()")
            if _IDENT.fullmatch(tick) and code_shaped(tick) and tick not in _KEYWORDS:
                refs.append(tick)
    return refs, defined


def resolve(ref: str, names: dict[str, set[str]], defined: set[str]) -> str:
    """``in-graph`` / ``unverifiable`` (an external import) / ``defined`` (by the agent) / ``hallucinated``."""
    head, last = ref.split(".", 1)[0], ref.rsplit(".", 1)[-1]
    if ref in defined or head in defined or last in defined:
        return "defined"
    if ref in names["ids"] or ref in names["quals"] or ref in names["modules"] or ref in names["paths"]:
        return "in-graph"
    if "." not in ref and ref in names["names"]:
        return "in-graph"
    if ref.endswith(".py") or ref.endswith(".go") or ref.endswith(".ts"):
        return "in-graph" if any(p.endswith("/" + ref) or p == ref for p in names["paths"]) else "hallucinated"
    if "." in ref:
        # a qualified reference resolves when its module-ish head is a
        # graph module and its last segment a symbol name there; or when
        # the head is an external import.
        if head in names["ext"] or ref.rsplit(".", 1)[0] in names["ext"]:
            return "unverifiable"
        if last in names["names"] and (head in names["modules"] or any(m.split(".")[-1] == head for m in names["modules"])):
            return "in-graph"
        return "hallucinated"
    return "hallucinated"


def score_transcript(messages: list[dict], names: dict[str, set[str]]) -> dict:
    refs, defined = references(messages)
    buckets = {"in-graph": 0, "unverifiable": 0, "defined": 0, "hallucinated": 0}
    invented: dict[str, int] = {}
    for r in refs:
        b = resolve(r, names, defined)
        buckets[b] += 1
        if b == "hallucinated":
            invented[r] = invented.get(r, 0) + 1
    judged = buckets["in-graph"] + buckets["hallucinated"]
    hsr = round(buckets["hallucinated"] / judged, 4) if judged else None
    return {"references": len(refs), **buckets, "hsr": hsr,
            "invented": sorted(invented, key=lambda k: (-invented[k], k))[:12]}


def patch_files(patch: str) -> list[str]:
    from hobbes.ttt.units import files_in_patch
    return files_in_patch(patch)


def rfe(edited: list[str], interior: list[str]) -> dict:
    e, i = set(edited), set(interior)
    inter = e & i
    return {"jaccard": round(len(inter) / len(e | i), 4) if (e | i) else None,
            "precision": round(len(inter) / len(e), 4) if e else None,
            "recall": round(len(inter) / len(i), 4) if i else None,
            "edited": sorted(e), "outside": sorted(e - i)}


def manifest_ignore(messages: list[dict], edited: list[str], unit: dict) -> dict:
    """An aided arm's agent denying what the manifest names, or editing only elsewhere."""
    named = [p for p in unit.get("paths", [])] + [t for t in unit.get("guarding_tests", [])]
    denials = []
    for m in messages:
        if m.get("role") != "assistant" or not m.get("content"):
            continue
        for sentence in re.split(r"(?<=[.!?\n])\s+", m["content"]):
            if _DENIAL.search(sentence):
                hit = [n for n in named if n in sentence or n.rsplit("/", 1)[-1] in sentence]
                if hit:
                    denials.append({"named": hit[:3], "text": sentence.strip()[:200]})
    elsewhere = bool(edited) and bool(unit.get("paths")) and not (set(edited) & set(unit["paths"]))
    return {"denials": denials, "edits_elsewhere": elsewhere, "ignored": bool(denials) or elsewhere}


def read_transcript(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def score_run(run_row: dict, unit: dict, names: dict[str, set[str]], aided: bool) -> dict:
    messages = read_transcript(run_row.get("transcript", ""))
    edited = patch_files(run_row.get("patch") or "")
    out = {"unit": unit["id"], "arm": run_row["arm"], "model": run_row.get("model"),
           "outcome": "error" if run_row.get("error") else ("patch" if edited else "empty-patch"),
           "turns": (run_row.get("envelope") or {}).get("num_turns"), "wall_s": run_row.get("wall_s"),
           "shared_run": run_row.get("shared_run", False),
           **{f"hsr_{k}": v for k, v in score_transcript(messages, names).items()},
           "rfe": rfe(edited, unit.get("paths", [])),
           "applies": bool(edited)}
    out["manifest_ignore"] = manifest_ignore(messages, edited, unit) if aided else None
    return out


# ---------------------------------------------------------------- report

def cell_report(scores: list[dict], resamples: int = 5_000, seed: int = 0) -> dict:
    """Per-arm means and the design's comparisons, paired by unit (`hobbes.ttt.report.paired`)."""
    from hobbes.ttt.report import paired
    metrics = {
        "hsr": lambda s: s["hsr_hsr"],
        "rfe_jaccard": lambda s: s["rfe"]["jaccard"],
        "rfe_precision": lambda s: s["rfe"]["precision"],
        "rfe_recall": lambda s: s["rfe"]["recall"],
        "manifest_ignore": lambda s: (None if s["manifest_ignore"] is None else float(s["manifest_ignore"]["ignored"])),
        "applies": lambda s: float(s["applies"]),
    }
    table: dict[str, dict[str, dict[str, float]]] = {}
    for s in scores:
        for metric, fn in metrics.items():
            v = fn(s)
            if v is not None:
                table.setdefault(metric, {}).setdefault(s["arm"], {})[s["unit"]] = v
    out: dict = {"arms": {}, "comparisons": {}, "n_units": len({s["unit"] for s in scores})}
    for metric, arms in table.items():
        for arm, vals in arms.items():
            out["arms"].setdefault(arm, {})[metric] = {"n": len(vals), "mean": round(statistics.mean(vals.values()), 4)}
        for a, b in (("A2", "A1"), ("A2", "A0"), ("A3", "A1"), ("A3", "A2"), ("A1", "A0")):
            if a in arms and b in arms:
                p = paired(arms[a], arms[b], None, resamples, seed)
                if p is not None:
                    out["comparisons"][f"{metric}:{a}-{b}"] = p.__dict__
    for arm in out["arms"]:
        rows = [s for s in scores if s["arm"] == arm]
        out["arms"][arm]["outcomes"] = {k: sum(1 for s in rows if s["outcome"] == k) for k in ("patch", "empty-patch", "error")}
        out["arms"][arm]["hsr_totals"] = {k: sum(s[f"hsr_{k}"] for s in rows) for k in ("references", "in-graph", "unverifiable", "defined", "hallucinated")}
    return out


def format_cell_report(rep: dict) -> str:
    metrics = ["hsr", "rfe_jaccard", "rfe_precision", "rfe_recall", "manifest_ignore", "applies"]
    lines = [f"units {rep['n_units']}", "arm   " + "".join(f"{m:>17}" for m in metrics) + "   patch/empty/error   refs (hall/unver/def)"]
    for arm, row in sorted(rep["arms"].items()):
        cells = "".join(f"{row[m]['mean']:>17.3f}" if m in row else f"{'-':>17}" for m in metrics)
        o, h = row["outcomes"], row["hsr_totals"]
        lines.append(f"{arm:5} {cells}   {o['patch']}/{o['empty-patch']}/{o['error']}   "
                     f"{h['references']} ({h['hallucinated']}/{h['unverifiable']}/{h['defined']})")
    lines += ["", "comparison                    n    Δ(a−b)     95% CI                 p      a>b   a<b"]
    for key, p in rep["comparisons"].items():
        lines.append(f"{key:29} {p['n']:4d}  {p['delta']:+.4f}   [{p['ci_low']:+.4f}, {p['ci_high']:+.4f}]   "
                     f"{p['p']:.4f}  {p['higher']:4d}  {p['wins']:4d}")
    lines += ["", "HSR: hallucinated / (in-graph + hallucinated) over the code-shaped references an agent emitted; "
              "external imports are unverifiable, names its own edits define are excluded. RFE against the unit's "
              "interior. manifest_ignore: an aided arm denied a manifest-named file or test, or edited only outside "
              "the manifest. applies: a non-empty patch — recorded, not gated. Every arm is model + prompt (P12)."]
    return "\n".join(lines)
