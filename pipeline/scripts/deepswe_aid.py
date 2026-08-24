"""Build a Pier prompt template = task instruction + Hobbes's ADR-077 aid.

ADR-078. Deterministic prototype of the injection (handoff REDIRECT step 3): the
planner LLM stage is NOT run here; files/symbols come from `hobbes plan`'s
lexical seeds plus graph symbols the instruction names, the neighborhood
from the symbol graph, the tests from tests.json. The aid is spliced from
hobbes.run.stages.aided_brief so the wording is the one ADR-077 pinned.
"""
import json, re, sys
from pathlib import Path
# run from pipeline/: `uv run scripts/deepswe_aid.py <task-dir> <repo> <plan.json> <out.j2>`
from hobbes.run.stages import aided_brief

task_dir, repo, plan_json, out = map(Path, sys.argv[1:5])
instruction = (task_dir / "instruction.md").read_text()
graph = json.loads((repo / ".hobbes/derived/graph.json").read_text())
tests = json.loads((repo / ".hobbes/derived/tests.json").read_text())
plan = json.loads(plan_json.read_text())

seed_mods = list(plan.get("seeds", {}).keys())
node_by_id = {n["id"]: n for n in graph.get("nodes", [])}
files = [node_by_id[m].get("path") or m for m in seed_mods if m in node_by_id]

words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+", instruction))
symbols = []
for s in graph.get("symbols", []):
    name = s.get("name") or s.get("id", "").rsplit(".", 1)[-1]
    mod = s.get("module") or ""
    if name in words and name[:1].isupper() and mod and not mod.split(".")[0].startswith("test") and not mod.endswith("_main"):
        symbols.append(f"{mod}.{name}")
symbols = sorted(set(symbols))[:20]

guarding = []
for t in tests.get("tests", []):
    reach = t.get("reaches_modules") or t.get("reaches") or []
    path = t.get("path") or t.get("file") or t.get("id") or ""
    toks = set(re.findall(r"[a-z]+", Path(path).stem.lower()))
    lw = {w.lower().rstrip("s") for w in words}
    if any(m in reach for m in seed_mods) and any(tok.rstrip("s") in lw for tok in toks - {"test", "tests"}):
        guarding.append(path)
guarding = sorted(set(filter(None, guarding)))[:8]

plan_stage = {"files": files, "symbols": symbols, "tests": guarding, "approach": "", "handoff": ""}
brief = aided_brief(instruction, plan_stage, graph)
aid = brief.split("## What Hobbes can see", 1)[1].split("## How to work", 1)[0]
aid = "## What Hobbes can see" + aid.rstrip()
aid = aid.replace("\n", "\nderived without a planner pass: files from lexical seeds, symbols by name match (C-55)\n", 1)

# Declaration-site spans (C-37: a pin is a declaration site). A bare file
# name on a large file invites a linear read of the whole file — the first
# 27B run read all 1,085 lines of _models.py because that was all it was
# told (benchmark-hypotheses.md, 2026-08-22). The graph knows the lines.
sym_by_id = {s["id"]: s for s in graph.get("symbols", [])}
def span(sid):
    s = sym_by_id.get(sid)
    if not s or not s.get("line"):
        return None
    mod = node_by_id.get(s.get("module", ""), {})
    path = mod.get("path") or s.get("path") or s.get("module", "")
    return f"{sid}  ({path}:{s['line']}-{s.get('end_line', s['line'])}, {s.get('kind', '?')})"
named = [span(x) for x in symbols]
# members of a named class that the instruction's words touch (e.g. iter_raw for "streaming"),
# plus every member whose name appears in the instruction — the unknown lines inside the class.
members = []
for sid, s in sym_by_id.items():
    owner = sid.rsplit(".", 1)[0]
    if owner in symbols and (s.get("name") in words or any(w.lower() in (s.get("name") or "").lower() for w in ("iter", "aiter", "stream", "close", "content") )):
        members.append(span(sid))
hood_ids = [h.strip() for line in aid.splitlines() if line.startswith("  it calls") or line.startswith("  callers") for h in line.split(":", 1)[1].replace("…", "").split(",")]
hood = [span(h) for h in hood_ids]
sites = [x for x in named + sorted(set(filter(None, members))) + sorted(set(filter(None, hood))) if x]
if sites:
    aid += "\n\ndeclaration sites (read these ranges first; the rest of each file is not where the change starts):\n" + "\n".join("  " + x for x in sites[:40])
template = "{{ instruction }}\n\n<<<HOBBES_CONTEXT>>>\n" + aid + "\n<<<END_HOBBES_CONTEXT>>>\n"
out.write_text(template)
print(template)
