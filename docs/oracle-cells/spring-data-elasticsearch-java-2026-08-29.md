# Oracle cell — spring-projects/spring-data-elasticsearch, module `.`, 2026-08-29

Repo: https://github.com/spring-projects/spring-data-elasticsearch (Apache-2.0), clone at `~/.hobbes/bench/oracle/repos/spring-data-elasticsearch`, commit cc7bd2b729efbe05092fff16e91ef94feccdd189 (shallow). **Drawn at random** from a seeded sample of GitHub's `language:java stars:300..3000 pushed:>2026-03-01` (seed 20260829, `random.shuffle`, first draw) — not chosen for shape. A large Maven library: **739 Java files**, heavy interface/implementation layering (repositories, converters, client abstractions), Kotlin extensions present but not indexed (no Kotlin lane A, ADR-096). Ingest SHA cc7bd2b7 (dirty: the `.gitignore` line, ADR-012). Hobbes at 6409bd4 + the working tree of the O8 build. Lane B on, scip-java 0.13.1 in the sandbox image, Temurin JDK 21 (derived). Oracle `javac 21.0.12.1+1-LTS` over the repo's own Maven build, 739 shards, contained.

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/spring-data-elasticsearch . ~/.hobbes/bench/oracle/spring-data-elasticsearch-java --lang java`. Runtime 52 s with the ingest, 24 s on a regrade.

## Numbers (report.txt, verbatim; the 8,214 `missed` rows elided)

```
cell   oracle javac 21.0.12.1+1-LTS (resolution)  sha cc7bd2b7
oracle ran contained (ADR-092)
hobbes edges 16050: confirmed 16050  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (16050/16050)
recall 66.4% (16238/24452 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 16251; misses map[interface→anonymous-member:513 interface→method:7469 static→anonymous-member:5 static→constructor:227]
  recall[interface→anonymous-member]   0.0% (0/513)  misses 513 = 6.2% of all misses
  recall[interface→method  ]  57.4% (10064/17533)  misses 7469 = 90.9% of all misses
  recall[static→anonymous-member]   0.0% (0/5)  misses 5 = 0.1% of all misses
  recall[static→constructor]  91.1% (2329/2556)  misses 227 = 2.8% of all misses
  recall[static→method     ] 100.0% (3845/3845)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 16050  contradicted 0  abstract 0  silent 0
  line-grain tolerance used on 8964 edge(s) (several oracle sites on one line)
poison check: PASS — 16050 seeded wrong edges: 16050 refused, 0 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/spring-data-elasticsearch: 24s
```

| bucket | count |
|---|---|
| hobbes edges | 16,050 |
| confirmed | 16,050 |
| contradicted | **0** |
| silent | 0 |
| precision-against-oracle | **100.0%** (16,050/16,050) |
| in-repo oracle pairs | 24,452 |
| recall (no roots; every resolved site) | **66.4%** (16,238/24,452) |
| external oracle pairs (not graded) | 16,251 |
| tiers | semantic 16,050 / 0 / 0 |

**Graph:** 944 nodes, 6,326 module edges, 9,058 symbols, 12,832 `calls` edges — **every one semantic**. 1,341 tests. Capture 100.0% of 33,559 detected call sites; 300 *seen and not modelled by design* (below-floor 297, local-binding 3) and **3 unresolved in the whole repo**. Containment `all_contained: true`. Dependency coverage 17 of 25 declared groups resolved; the 8 unresolved are optional integrations and Kotlin artifacts nothing in the compiled Java references (C-69's read-not-resolved shape).

## Lane agreement — 3,908 dual-resolved sites, 2 disagreements (0.05%)

Both remaining rows are the **same-line collision**: `RequestConverter.java:1602` and `:1612` each hold *two* calls named `getHighlight` —

```java
.map(highlightQuery -> new HighlightQueryBuilder(…, this)
        .getHighlight(highlightQuery.getHighlight(), highlightQuery.getType()))
```

— the two-argument chain continuation and the zero-argument accessor on a value. The join keys evidence on `(file, line, name)` and tie-breaks by column, and with two identically named calls on one line the two lanes can pair with different ones. Not a resolver being wrong on either side: the graded edge is semantic and javac confirmed it. Registered as **C-70** (this cell is its measurement: 2 of 3,908 dual-resolved sites, 0.05%); the same shape is what the oracle reports from its side as `line-grain tolerance used on 8,964 edges`.

**A third disagreement was a real lane A defect and is fixed.** `new CriteriaQuery( //` (a trailing comment inside the argument list) bound to the two-argument constructor, because tree-sitter *extras* — comments — are named children and the arity filter counted one. `_args` now skips comment nodes; the pinned test is `test_a_comment_inside_an_argument_list_is_not_an_argument`. Disagreements 3 → 2.

## Contradicted (0)

None.

## Misses by class (8,214 rows)

- **interface→method, 7,469 (90.9%), recall 57.4%.** This is the interface-layered repo the class was predicted for: the declared method is drawn and confirmed, each concrete implementation below it is a miss. **The lowest `interface→method` recall of the three semantic Java cells** (jsoup 67.5%, petclinic 98.7%) — the shape of the codebase, not of the extractor, and exactly the number C-58's Java entry needed.
- **interface→anonymous-member 513 + static→anonymous-member 5 (6.3%).** Overrides declared in anonymous class bodies — below the symbol floor (C-9), named `local-binding` in the tail.
- **static→constructor, 227 (2.8%), recall 91.1%.** Chiefly `new T() {..}`, drawn as `uses` by decision.
- **static→method, 0 misses — recall 100.0% (3,845/3,845).** Every statically dispatched named call in a 739-file repo, drawn.

**Poison check:** PASS — 16,050 seeded wrong edges: 16,050 refused, 0 unjudged, 0 falsely confirmed.

**Direction of fix (before → after, signed):** `contradicted 634 → 0 (−634)`, `precision 96.0% → 100.0% (+4.0)` across the two oracle-side fixes recorded in the jsoup cell (the annotation-bearing key join, the synthetic/default constructors); `recall 66.0% → 66.4% (+0.4)`; lane disagreements `3 → 2 (−1, Hobbes-side, the comment-as-argument fix)`.

**Direction of fix for what remains (no proposals):** `interface→method` and the `anonymous-member` classes — neither side, by decision (C-58, C-9). `static→constructor` — Hobbes, if `new T() {..}` is ever to draw `calls`. The 2 lane disagreements — the join's `(file, line, name)` key, if per-column pairing is ever worth building.

**Not graded:** the 16,251 external oracle pairs (JDK, Spring, Elasticsearch client callees, by design). No repo was abandoned.
