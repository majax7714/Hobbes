# Oracle cell — spring-projects/spring-petclinic, module `.`, 2026-08-29

Repo: https://github.com/spring-projects/spring-petclinic (Apache-2.0), clone at `~/.hobbes/bench/oracle/repos/spring-petclinic`, commit 818c4136ea971c21674525f9053de0d9c7ad8cfe (shallow). Picked as the **Spring service** shape the Java plan named: 50 Java files, a Maven pom *and* a Gradle wrapper in the same directory (the ADR-096 rule picks Maven), constructor injection, JPA entities, `@GetMapping` controllers, JUnit 5 + Spring Boot test slices. Ingest SHA 818c4136 (the ingest reports a dirty tree: `hobbes ingest` appends `.hobbes/` to the clone's `.gitignore`, ADR-012 — nothing else changed). Hobbes at 6409bd4 + the working tree of the O8 build. Lane B on (`HOBBES_SCIP=1`), scip-java 0.13.1 in the sandbox image, Temurin JDK 21 (derived: the pom asks for release 17). Oracle `javac 21.0.12.1+1-LTS` over the repo's own Maven build, 50 shards, contained.

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/spring-petclinic . ~/.hobbes/bench/oracle/spring-petclinic-java --lang java`. Runtime 17 s with the ingest, 8 s on a regrade. Outputs in `~/.hobbes/bench/oracle/spring-petclinic-java/` (`hobbes.json`, `oracle.json`, `report.json`, `report.txt`, `javac-shards/`, `plugin/`).

## Numbers (report.txt, verbatim; the 6 `missed` rows elided)

```
cell   oracle javac 21.0.12.1+1-LTS (resolution)  sha 818c4136
oracle ran contained (ADR-092)
hobbes edges 356: confirmed 356  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (356/356)
recall 98.4% (367/373 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 1239; misses map[interface→method:4 static→constructor:2]
  recall[interface→method  ]  98.7% (293/297)  misses 4 = 66.7% of all misses
  recall[static→constructor]  95.6% (43/45)  misses 2 = 33.3% of all misses
  recall[static→method     ] 100.0% (31/31)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 356  contradicted 0  abstract 0  silent 0
  line-grain tolerance used on 125 edge(s) (several oracle sites on one line)
poison check: PASS — 356 seeded wrong edges: 356 refused, 0 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/spring-petclinic: 8s
```

| bucket | count |
|---|---|
| hobbes edges | 356 |
| confirmed | 356 |
| contradicted | **0** |
| silent | 0 |
| precision-against-oracle | **100.0%** (356/356) |
| in-repo oracle pairs | 373 |
| recall (no roots; every resolved site) | **98.4%** (367/373) |
| external oracle pairs (not graded) | 1,239 |
| tiers | semantic 356 / 0 / 0 |

**Graph:** 130 nodes, 389 module edges, 240 symbols, 296 `calls` symbol edges — **every one semantic**. Capture 100.0% of 1,607 detected call sites. Lane agreement 36 dual-resolved sites, **0 disagreements**. Containment `all_contained: true`, one step (`index-java`), escape hatch off. Dependency coverage 4 of 7 declared groups resolved; the three "missing" are build-only tooling (`checkstyle`, `spring-javaformat`, `nohttp`) that no source references — the C-69 shape, read not resolved.

## Contradicted (0)

None. Every Hobbes call edge in this cell is an edge javac itself resolved to the same declaration.

## Misses by class (6 rows)

- **interface→method, 4 (66.7%).** Calls through a Spring/JPA interface whose CHA override set holds a repository or service implementation the declared method does not name. C-58's Java face; the declared-target edge *is* drawn and confirmed, the override is the miss.
- **static→constructor, 2 (33.3%).** Both at `PetTypeFormatterTests.java:84,89` — `petTypes.add(new PetType() { … })`, an anonymous subclass. Hobbes draws `uses` of `PetType` there by decision (ADR-096: `new T() {..}` is not a lane A call site); the oracle names the superclass constructor the synthetic one calls.

**Poison check:** PASS — 356 seeded wrong edges: 356 refused, 0 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix (which side would need to change; no proposals):** `interface→method` — neither, by decision: the edge to the declared method is what Hobbes draws and the concrete overrides are C-58's registered hole; the number *is* the measurement. `static→constructor` (the 2 anonymous-subclass rows) — Hobbes, if `new T() {..}` is ever to draw a `calls` edge to T's constructor; today it is a recorded miss class, not a defect.

**Not graded:** the 1,239 external oracle pairs (JDK, Spring, JPA, AssertJ callees, by design). No repo was abandoned.
