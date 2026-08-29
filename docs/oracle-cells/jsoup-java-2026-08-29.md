# Oracle cell — jhy/jsoup, module `.`, 2026-08-29

Repo: https://github.com/jhy/jsoup (MIT), clone at `~/.hobbes/bench/oracle/repos/jsoup`, commit 7860d088e044236e288c1f88a743b68b2a0edece (shallow, 1.24.1-SNAPSHOT). Picked as the **Maven library** shape the Java plan named: 197 Java files, one flat reactor, no framework, an unusually test-heavy tree (1,716 JUnit tests — 22,239 of its 30,035 detected call sites are under `src/test`), and the enum-with-body and anonymous-class idioms that turned out to matter. Ingest SHA 7860d088 (dirty: the `.gitignore` line, ADR-012). Hobbes at 6409bd4 + the working tree of the O8 build. Lane B on, scip-java 0.13.1 in the sandbox image, Temurin JDK 21 (derived). Oracle `javac 21.0.12.1+1-LTS` over the repo's own Maven build, 197 shards, contained.

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/jsoup . ~/.hobbes/bench/oracle/jsoup-java --lang java`. Runtime 21 s with the ingest, 9 s on a regrade.

## Numbers (report.txt, verbatim; the 5,863 `missed` rows elided)

```
cell   oracle javac 21.0.12.1+1-LTS (resolution)  sha 7860d088
oracle ran contained (ADR-092)
hobbes edges 18627: confirmed 18627  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (18627/18627)
recall 76.2% (18767/24630 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 11063; misses map[interface→anonymous-member:407 interface→method:5226 static→anonymous-member:45 static→constructor:180 static→method:5]
  recall[interface→anonymous-member]   0.0% (0/407)  misses 407 = 6.9% of all misses
  recall[interface→method  ]  67.5% (10870/16096)  misses 5226 = 89.1% of all misses
  recall[static→anonymous-member]   0.0% (0/45)  misses 45 = 0.8% of all misses
  recall[static→constructor]  84.6% (989/1169)  misses 180 = 3.1% of all misses
  recall[static→method     ]  99.9% (6908/6913)  misses 5 = 0.1% of all misses
  tier semantic   confirmed 18621  contradicted 0  abstract 0  silent 0
  tier syntactic  confirmed 6  contradicted 0  abstract 0  silent 0
poison check: PASS — 18627 seeded wrong edges: 18627 refused, 0 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/jsoup: 9s
```

| bucket | count |
|---|---|
| hobbes edges | 18,627 |
| confirmed | 18,627 |
| contradicted | **0** |
| silent | 0 |
| precision-against-oracle | **100.0%** (18,627/18,627) |
| in-repo oracle pairs | 24,630 |
| recall (no roots; every resolved site) | **76.2%** (18,767/24,630) |
| external oracle pairs (not graded) | 11,063 |
| tiers | semantic 18,621 / 0 / 0 · syntactic 6 / 0 / 0 |

**Graph:** 250 nodes, 1,907 module edges, 4,588 symbols, 12,665 `calls` edges — 12,663 semantic, 6 syntactic (evidence lines). 1,716 tests. Capture 99.8% of 30,035 detected call sites; the remainder is 63 *seen and not modelled by design* (below-floor 19, local-binding 44) and 6 `fallback-resolved`. Lane agreement 3,417 dual-resolved sites, **0 disagreements**. Containment `all_contained: true`. Dependency coverage 5 of 5 declared groups resolved.

## Contradicted (0)

None — after two fixes this cell produced, both recorded below.

## What this cell fixed (the honest history of the number)

The first pass on this repo read **237 contradicted (98.7%)** and the second **102 (99.5%)**. Both were oracle-side defects, found and fixed here:

1. **Annotation-carrying parameter types broke the key join.** jsoup's jspecify `@Nullable` rides `TypeMirror.toString()`, so a *source*-compiled declaration keyed `Element#<init>(@Nullable String)` and the *class-file* symbol the test compilation resolved keyed `Element#<init>(java.lang.String)` — every test→main constructor missed its declaration and read contradicted. The plugin now builds erased parameter names from the element, never from `toString`.
2. **javac's synthetic `super()` and default constructors.** javac inserts `super();` at a constructor body's opening brace and synthesises a default constructor at the class line. The first counted as a site no source line makes (now skipped and counted in `excluded.synthetic`); the second was briefly dropped as a declaration, which cost every `new T()` on an implicit constructor its target — it is kept, because the class line is exactly where Hobbes draws that edge (the D-O4 rule for a call of a class).

Both are logged in `docs/oracle-defects.md` (H-20, H-21). No product change followed from either.

## What this cell fixed on the product side

The first ingest left **44 sites `unclassified`** — every one a bare call of a helper declared in an **enum constant's body** (`HtmlTreeBuilderState`'s `anythingElse(t, tb)`, 44 of them). scip-java gives such members `local` symbols, so neither lane could place them. Lane A now records anonymous- and enum-constant-body methods as **local bindings with the body's extent** (ADR-046's mechanism), so the tail names them `local-binding` — seen and deliberately not modelled — and `unclassified` on this repo is **0**. The oracle counts their call pairs as the `*→anonymous-member` miss classes (452 rows here), which is the same fact stated from the other side.

## Misses by class (5,863 rows)

- **interface→method, 5,226 (89.1%), recall 67.5%.** The CHA override set: Hobbes draws and confirms the *declared* method; each concrete override below it is a miss. C-58's Java face — the majority class, as the plan predicted.
- **interface→anonymous-member 407 + static→anonymous-member 45 (7.7%).** Overrides and helpers declared inside anonymous-class and enum-constant bodies — below the symbol floor by decision (C-9), and named `local-binding` in the tail.
- **static→constructor, 180 (3.1%), recall 84.6%.** Chiefly `new T() {..}` (drawn as `uses` of T by decision) and `super(new Tag(..), baseUri)`-shaped nested creations.
- **static→method, 5 (0.1%), recall 99.9%.** `super.clone()` overrides in `Comment`/`DataNode` and friends.

**Poison check:** PASS — 18,627 seeded wrong edges: 18,627 refused, 0 unjudged, 0 falsely confirmed.

**Direction of fix (before → after, signed):** `confirmed 18,373 → 18,525 → 18,627 (+254)`, `contradicted 237 → 102 → 0 (−237)`, `precision 98.7% → 99.5% → 100.0% (+1.3)`, `recall 75.8% → 76.5% → 76.2% (−/+, the denominator moved with the constructor rule)`, `hobbes edges 18,610 → 18,627 (+17, the enum-constant constructor sites lane A learned)`. Both precision fixes were **oracle-side**; the `unclassified 44 → 0` was **Hobbes-side**.

**Direction of fix for what remains (no proposals):** `interface→method` and the two `anonymous-member` classes — neither side, by decision (C-58, C-9): the numbers *are* the measurement. `static→constructor` — Hobbes, if `new T() {..}` is ever to draw `calls`. `static→method` (5 `super.clone()` rows) — Hobbes.

**Not graded:** the 11,063 external oracle pairs (JDK, JUnit callees, by design). No repo was abandoned.
