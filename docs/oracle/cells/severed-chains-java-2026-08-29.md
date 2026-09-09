# Oracle cell — Legend-of-Dragoon-Modding/Severed-Chains, module `.`, 2026-08-29

**The cell where lane B did not run — and the first Java cell that grades the syntactic floor alone.**

Repo: https://github.com/Legend-of-Dragoon-Modding/Severed-Chains (GPL-3.0), clone at `~/.hobbes/bench/oracle/repos/Severed-Chains`, commit 3841686e70a15803037359fe1f4545f0beec469f (shallow). **Drawn at random** from a seeded sample of GitHub's `language:java stars:300..3000 pushed:>2026-03-01` (seed 20260829, `random.shuffle`, second draw) — not chosen for shape, which is the point. A Gradle 9.1.0 build (`org.openjfx.javafxplugin`, `java-library`, `maven-publish`), **1,254 Java files**, `sourceCompatibility = targetCompatibility = JavaVersion.VERSION_25`. Ingest SHA 3841686e (dirty: the `.gitignore` line, ADR-012). Hobbes at 6409bd4 + the working tree of the O8 build. Oracle `javac 25.0.4.1+1-LTS` — the JDK derived from what the build spells (ADR-096 decision 2; the first pass failed with `invalid source release: 25` on the default JDK 21, which is what put the derivation in) — 1,253 shards, contained.

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/Severed-Chains . ~/.hobbes/bench/oracle/Severed-Chains-java --lang java`. Runtime 34 s with the ingest, 15 s on a regrade.

## Lane B did not run here (C-67, and the honest half of the cell)

`scip-java index --build-tool=gradle` **failed on this repo**: its own Gradle injection could not attach the SCIP compiler plugin, and it said so in its own words —

> … Workaround: apply the SCIP plugin earlier (e.g. via a settings plugin), or restructure the build so that `compileOnly` is not resolved at evaluation time. / 2. Another Gradle plugin is replacing the compiler arguments we add (rather than appending). … If `-Xplugin:scip` is missing from the printed javac command, another plugin is overwriting `JavaCompile.options.compilerArgs`.

So the per-unit degradation fired (`scip-java`, the C-26/C-67 pattern), the repo fell to **lane A's syntactic floor, whole**, and the ingest said so. This is the outcome `docs/java-build-plan.md` predicted as "the most common real-world outcome for enterprise repos", arriving on the second random draw.

**The oracle's own plugin attached on the same build**, through the init script (`java/hobbes-oracle.gradle`) rather than scip-java's injection — which is why this cell has an answer key at all. That asymmetry is worth stating plainly: Hobbes's grading harness reached a build its indexer could not, so the cell measures *lane A alone against javac*, which no other Java cell does.

## Numbers (report.txt, verbatim; the 41,717 `missed` rows elided)

```
cell   oracle javac 25.0.4.1+1-LTS (resolution)  sha 3841686e
oracle ran contained (ADR-092)
hobbes edges 10154: confirmed 10154  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (10154/10154)
recall 23.5% (12803/54520 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 19050; misses map[interface→anonymous-member:78 interface→method:35289 static→constructor:2560 static→method:3790]
  recall[interface→anonymous-member]   0.0% (0/78)  misses 78 = 0.2% of all misses
  recall[interface→method  ]   0.4% (148/35437)  misses 35289 = 84.6% of all misses
  recall[static→constructor]  77.8% (8947/11507)  misses 2560 = 6.1% of all misses
  recall[static→method     ]  49.5% (3708/7498)  misses 3790 = 9.1% of all misses
  tier syntactic  confirmed 10154  contradicted 0  abstract 0  silent 0
  line-grain tolerance used on 4438 edge(s) (several oracle sites on one line)
poison check: PASS — 10154 seeded wrong edges: 10154 refused, 0 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/Severed-Chains: 15s
```

| bucket | count |
|---|---|
| hobbes edges | 10,154 — **all syntactic tier** |
| confirmed | 10,154 |
| contradicted | **0** |
| silent | 0 |
| precision-against-oracle | **100.0%** (10,154/10,154) |
| in-repo oracle pairs | 54,520 |
| recall (no roots; every resolved site) | **23.5%** (12,803/54,520) |
| external oracle pairs (not graded) | 19,050 |

**Graph:** 1,344 nodes, 7,474 module edges, 9,898 symbols, 3,955 `calls` edges — **0 semantic**, every one lane A's fallback. Capture 0.0% of 51,969 detected sites *by the resolution measure* (nothing resolved semantically, which is the degradation showing through the number as it should); the tail classifies the whole remainder — attr-call 32,474, fallback-resolved 12,569, import-binding 4,174, overload-set 1,770, inherited-member 496, builtin-name 376, unclassified 110 (0.2%). Lane agreement compares 0 sites (only one lane answered). Containment `all_contained: true`.

## What this cell proves

- **Lane A's Java resolver does not draw wrong edges at scale.** 10,154 syntactic edges, every one confirmed by javac, **zero contradicted**, on a 1,254-file repo the resolver had never seen. The abstention rules ADR-096 chose — arity filtering, stopping at a type with supertypes, declining an overload set — are what buy that: 1,770 `overload-set` and 496 `inherited-member` sites are *declined*, not guessed.
- **And it is a floor, not a graph.** 23.5% recall: the fallback reaches roughly a quarter of what the compiler resolves, and `interface→method` alone is 35,289 of the 41,717 misses (84.6%) — this repo is written against interfaces, so with no semantic lane there is almost nothing to draw. C-8's cost, measured on a real repo for the first time in Java.

## Misses by class (41,717 rows)

- **interface→method, 35,289 (84.6%), recall 0.4%.** With no semantic lane, a call through an interface has nothing to resolve *to*: lane A declines a value's method call by construction (`dotted`), so neither the declared method nor its overrides are drawn. Under lane B this class recovers to 57–99% (the other three cells).
- **static→method, 3,790 (9.1%), recall 49.5%.** Calls lane A's fallback cannot place: a method on a value, an inherited overload, a static import through a wildcard.
- **static→constructor, 2,560 (6.1%), recall 77.8%.** `new T(..)` where T is a wildcard-imported or otherwise unplaceable type, plus the anonymous-subclass class (ADR-096).
- **interface→anonymous-member, 78 (0.2%).** An override declared in an anonymous class body — below the symbol floor by decision (C-9).

**Poison check:** PASS — 10,154 seeded wrong edges: 10,154 refused, 0 unjudged, 0 falsely confirmed.

**Direction of fix (which side would need to change; no proposals):** the four miss classes — Hobbes, and all four are the *same* fix: lane B running here. `interface→method` at 0.4% is not a lane A defect, it is C-8's floor. The scip-java Gradle injection failure is upstream (P9, `scip-java` 0.13.1) and registered as **C-67**; a Gradle repo whose build another plugin owns gets lane A only, disclosed. Precision 0 contradicted — nothing to fix on the Hobbes side of the edges that *were* drawn.

**Not graded:** the 19,050 external oracle pairs (JDK, JavaFX, LWJGL callees, by design). No repo was abandoned.
