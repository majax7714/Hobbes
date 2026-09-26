"""Cross-repo duplicates in the pool: every union member (ISA or body-shape, non-thin) keyed by the sha1 of
its whitespace-normalised, comment-stripped body. A task whose body appears in an earlier taken repo (pool
order) is a duplicate, never a second training example. Writes dedupe.json."""
import hashlib, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "family-count"))
import count  # noqa: E402
import measure  # noqa: E402

pool = json.load(open(HERE / "pool.json"))["order"]
halves = json.load(open(HERE / "halves.json"))
taken = halves["first"] + halves["second"]
seen, out = {}, {}
for name in taken:
    key = name.replace("/", "__")
    t = time.time()
    repo = count.Repo(key, HERE / "repos" / key)
    nonthin = [m for m in repo.members.values() if not m["thin"]]
    isa = measure.isa_families(nonthin)
    body, _, _ = measure.body_families(count.loose_groups(nonthin))
    union = {m["id"]: m for f in isa + body for m in f["members"]}
    dup, first = 0, 0
    own = set()
    for m in union.values():
        h = hashlib.sha1(" ".join((m["body"] or "").split()).encode()).hexdigest()
        if h in seen and seen[h] != key:
            dup += 1
        elif h in own:
            dup += 1  # the same body twice in one repo (an #if arm, a copied file)
        else:
            first += 1
            seen.setdefault(h, key)
        own.add(h)
    out[name] = {"union": len(union), "unique": first, "duplicate": dup, "seconds": round(time.time() - t, 1)}
    print(name, out[name], flush=True)
out["_total"] = {"union": sum(v["union"] for v in out.values()), "unique": sum(v["unique"] for v in out.values()),
                 "duplicate": sum(v["duplicate"] for v in out.values())}
(HERE / "dedupe.json").write_text(json.dumps(out, indent=1))
print("TOTAL", out["_total"])
