"""E3's pool: the GitHub search union, as DRAW-RULE.md states it. stdlib + `gh api`."""
import json, random, subprocess, time, sys

KW = "simd avx2 avx512 neon sse intrinsics vectorized".split()
LIC = "mit apache-2.0 bsd-2-clause bsd-3-clause isc zlib unlicense cc0-1.0 bsl-1.0 0bsd".split()

def query(q, page):
    while True:
        r = subprocess.run(["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={q}",
                            "-f", "per_page=100", "-f", f"page={page}"], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        if "rate limit" in (r.stdout + r.stderr).lower():
            time.sleep(65); continue
        raise SystemExit(f"query failed: {q} p{page}: {r.stdout} {r.stderr}")

queries, repos = [], {}
for kw in KW:
    for lic in LIC:
        q = f"{kw} in:name,description,topics,readme language:C license:{lic} stars:>=20"
        page, got, total = 1, 0, None
        while True:
            d = query(q, page); time.sleep(2.2)
            total = d["total_count"]
            for it in d["items"]:
                repos.setdefault(it["full_name"], {
                    "full_name": it["full_name"], "fork": it["fork"], "archived": it["archived"],
                    "default_branch": it["default_branch"], "size": it["size"],
                    "stars": it["stargazers_count"], "owner": it["owner"]["login"],
                    "spdx": (it.get("license") or {}).get("spdx_id"), "language": it.get("language")})
            got += len(d["items"])
            if got >= min(total, 1000) or not d["items"]:
                break
            page += 1
        queries.append({"q": q, "total_count": total, "returned": got, "truncated": total > 1000})
        print(f"{total:>5} {got:>5} {q}", flush=True)

names = sorted(repos)
random.Random(20260926).shuffle(names)
json.dump({"queries": queries, "union": len(names), "order": names,
           "repos": [repos[n] for n in names]}, open("pool.json", "w"), indent=1)
print("union", len(names))
