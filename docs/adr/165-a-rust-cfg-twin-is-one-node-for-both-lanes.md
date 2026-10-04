# ADR-165 — A Rust cfg twin is one node for both lanes, and its lane disagreement is a registered shape

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **1** of three, then, when the probe
overturned its premise, "map to the node" of three) and **built** (0.2.89-beta) · **Owner:** Max ·
**Source:** CI run 37127474375 (the `graph` job, `hobbes lanes`, on `3f95d67`), then this ADR's step 0
and regrade (`~/.hobbes/bench/c182-rust-cfg-twins/`).

Amends ADR-123 §1 (a third shape), ADR-163 (which same-header repeats "stay the node's") and architecture
§3.4. Registers **C-182** (surfaced). Draws one more kind of edge: a call lane B resolves onto a cfg twin's
later arm.

## What is wrong

ADR-163 added the `minirustimpl` fixture, which includes memchr's cfg-twin shape on purpose:
`src/cow.rs` writes `pub fn width` twice, under `#[cfg(feature = "alloc")]` (line 12) and
`#[cfg(not(feature = "alloc"))]` (line 17). Both defs mint `src/cow.width`; the node is the first. ADR-163
excluded such a qualname from its refusal ("a cfg twin … stays the node's, as before").

The fixture sits in this repo, so CI's self-ingest graphs it. At `lib.rs:24`, `cow::width(bytes)`:

- lane A's fallback names the node's def, `cow.rs:12` (it reads no features);
- lane B (rust-analyzer, default features, `alloc` off) names the arm it compiled, `cow.rs:17`.

`hobbes lanes` compares answers by `(file, line)`, no registered shape explained the row, and the job
exited 1. The ADR-163 session ran pytest with `lane_b` and the memchr and dagger cells on the host, but not
`scripts/ci-graph.sh`; a cell regrade does not run `hobbes lanes` on this repo.

**The first route's premise was wrong.** Route 1 as first proposed only named the row, on the claim that
both answers are one node and so the edge is the same. The probe showed otherwise: line 17 starts no
symbol the projection knows, so lane B's answer fell `below-floor` (blaming C-58), and lane B having
answered, lane A's fallback was not drawn either. The graph drew **no** `measure → cow.width` edge.
ADR-163's test, "the cfg twin still draws", covered calls written *inside* the later arm, never calls
*onto* it. Shaping the row alone would have called a dropped edge explained. Max chose to map it.

**And not every same-header repeat is a twin.** ADR-163's exclusion was "headers all alike". On memchr
that is 161 ids, but 152 of them are not one item under two `cfg` arms: the `benchmarks/haystacks` file is
a copy of the standard library kept as search input, which no crate compiles, and it repeats names freely
(`struct B` at 12972, `const B` at 37963). In a crate that compiles, Rust's type and value namespaces allow
the same pair. Mapping lane B's answer onto such a "later arm" would draw a wrong edge at `semantic`.

## Measured (step 0)

A twin is a qualname with two or more defs in one file whose impl headers are all the same, whose kinds
are all the same, and each of which a `#[cfg(…)]` gates, on the item or on an enclosing `mod`/`impl`
(`cfg_attr` does not count: it gates an attribute).

| repo | same-header repeats (ADR-163's exclusion) | cfg twins (this rule) | lane rows of this shape |
|---|---:|---:|---:|
| memchr | 161 (156 in `haystacks`) | 9 (4 in `haystacks`, std's own `cfg(test)` pairs) | 0 |
| dagger `sdk/rust` | 0 | 0 | 0 |
| rust_proj | 0 | 0 | 0 |
| this repo (`minirustimpl`) | 2 | 2 (`Imp`, `width`) | 1 |

## The decision (Max: map to the node)

1. **Lane A lists the twins** by the rule above: `rustsource.cfg_twins`, per file, each twin's def spans.
   `RustFile.cfg_gated` records which defs a `cfg` gates. The bundle carries `cfg_twins`.
2. **At the projection, a twin's other arms are the node's, both ways** (`project(…, twins=)`): a fact
   written inside one is filed under the node, and a fact resolved onto one draws to the node, at the
   tier its lane gives it. The arms join both of `_SymbolIndex`'s lookups; ADR-155's Python later defs
   join only the enclosing one, because there lane B names the first def.
3. **A third lane shape, `cfg-twin` (C-182)**, tried after `same-line-pair` and before `cpp-withheld`:
   lane A's guess is the start of one arm of a twin, and lane B's answer lies inside a *different* arm of
   the same twin, in the same file. With (2) both answers draw the one edge, so the row is explained
   completely. A guess and answer inside one arm, or in two different twins, stay unexplained.
4. **One degradation record per ingest with a twin**, stage `rust-cfg-twins`, naming C-182, with
   examples and their def lines. `list_blind_spots` and the ingest summary show it.
5. `hobbes lanes` cites C-182 beside the shape's count; exit 3 when every row has a shape (ADR-123 §2).

A same-header repeat that is not a twin by this rule is unchanged: neither refused (C-180) nor mapped.
That residual is registered in C-182 and noted in `currently-open.md`.

## Alternatives considered

- **Shape the row and draw nothing** (the first route as proposed). It hides a dropped true edge.
- **Refuse, and tail the site as `cfg-twin` instead of `below-floor`.** Honest, but it draws less than the
  index proves: lane B answered with the item's own compiled body.
- **Compare lanes by node id instead of `(file, line)`.** It would also hide C-180's rows.
- **Twins by header alone (ADR-163's exclusion).** 152 of memchr's 161 would map different items.
- **Tell the arms apart (read the build's features).** The prevention; it needs `cargo metadata`'s feature
  set in lane A and changes symbol ids. Not built; C-182 records it.

## Built (0.2.89-beta)

`extract/rustsource.py` (`_is_cfg_attr`, the `gated` walk, `RustFile.cfg_gated`, `cfg_twins`, the bundle
key), `extract/scipsource.py` (`project(…, twins=)`, `_SymbolIndex`), `extract/evidence.py` (`CFG_TWIN`,
`disagreement_shapes(…, twins=)`), `extract/__init__.py` (the twin arms, `_lane_agreement(…, twins=)`,
`_cfg_twin_record`), `cli.py` (`_SHAPE_CONSTRAINTS`). Tests: `test_evidence.py::TestDisagreementShapes`
(the shape, its near misses), `test_shared_qualnames.py` (the gate's near misses, the projection both ways,
the fixture's row with lane B's answer hand-built, the record, and the `lane_b` ingest on the host),
`test_cli.py::TestLanes`.

**Regrade** (`~/.hobbes/bench/c182-rust-cfg-twins/`: `regrade3.sh`, `cells.tsv`, `measure_twins.py`; the
before arm is ADR-163's after arm, since `3f95d67` moved only Python): memchr 919 → 919 confirmed,
0 contradicted, strict 100%, poison clean; its edges, symbols, module edges and coverage are byte-identical
(none of its twins' later arms is a lane B answer). dagger and rust_proj have no twins and cannot move.
The fixture gains `measure → cow.width` at `semantic` and loses its `below-floor` site.

## Amendment — 2026-10-03: the residual is refused or named (0.2.95-beta)

**Status:** accepted (Max, 2026-10-03, the proposed route). C-182 was partial: a same-header repeat that is
not a twin was neither refused nor mapped, and no record named it.

**Measured** (lane A's own read, `rustsource`): memchr 5 two-kinds ids and 147 other repeats, every one in
`benchmarks/haystacks`; dagger `sdk/rust` and this repo 0 of either.

1. **Two kinds are two items.** `shared_qualnames` also lists an id whose defs are of more than one kind,
   whatever its headers, so a fact written inside or resolved onto a later def is refused as C-180's are,
   counted in the `rust-qualnames` record and tailed `shared-qualname`.
2. **The rest is named.** `same_header_repeats` lists, by file, every other repeat that is not a twin; one
   `rust-repeats` record per ingest names the count, the files and examples with their def lines, and this
   ADR. Their behaviour is unchanged: the node is the first def and a later def's facts are filed under it.
   No crate that compiles can write this shape, so lane B has nothing there to disagree with.
3. C-182 is surfaced. The `minirustimpl` fixture gains `haystacks/std.rs`, a file no target includes, with
   both shapes.

**Regrade** (`~/.hobbes/bench/c182-residual/`: `regrade3.sh`, `cells.tsv`, `after/`; before is this ADR's
own after arm): memchr 919 → 919 confirmed, 0 contradicted, syntactic-confirmed 7 → 7, poison clean; symbols
identical; 2 evidence rows removed, both lane A calls in `haystacks/code/rust-library.rs` onto the later
def of the two-kinds `vec` (lines 7640, 9828), none outside `haystacks`. The `rust-qualnames` record counts
174 ids, the `rust-repeats` record 147 in one file.

## Second amendment — 2026-10-04: the node sits at the compiled arm; a reference in an uncompiled arm is refused (0.2.116-beta)

**Status:** accepted (Max, 2026-10-04, Route 1 of the forty-third session: "the node's line follows the arm
lane B indexed", probed first) and **built**. Step 0's probe on leaf's cached lane B facts
(`~/.hobbes/bench/c182-compiled-arm-2026-10-04/`) confirmed the premise and found a second fact:

- **Confirmed:** rust-analyzer writes a *definition* only in the arm the build compiles. leaf's `crypto.rs`
  has 21 definitions in `mod aead`'s second arm (211–352) and none in its first (44–206); every one of the
  44 contradicted rows is a call from compiled code onto the twin, drawn to a line in the first arm.
- **New, and the record was wrong:** rust-analyzer still writes *references* inside the uncompiled arm,
  resolved against the compiled arm's scope. 108 references in `crypto.rs`, 40 of them inside lines 44–206;
  17 of those carry a name their token does not spell, 15 on a `self` or `super` keyword naming a module
  (`self.cipher` read as `aead`). C-182's
  "lane B indexes only the compiled arm" was false, and 23 `semantic` `uses` edges were drawn from code the
  build does not compile. The MIR key grades calls, so no grade could see them: an unnamed limit
  (precedent 1).

1. **The compiled arm** (`rustsource.compiled_arms`): an arm of a twin holding a lane B definition line is
   compiled. Where exactly one arm is, the node's `line`/`end_line` move to it before the other arms are
   read, so the node is the code the build runs. Lane B silent on the file, or two arms defined, names none:
   the node stays at its first arm, as before. Ids do not change.
2. **The uncompiled region:** for each other arm of such a twin, the widest `#[cfg]`-gated item around it
   (its attributes included; `RustFile.cfg_gates` records the chain) that holds no lane B definition, else
   the arm itself. leaf's is the whole first `mod aead`, its `impl` headers included.
3. **Refused, before the join:** every lane B reference written inside such a region. It reaches no edge or
   row; lane A's facts there stay `syntactic` (C-182: lane A files every arm's calls under the node). The
   `rust-cfg-twins` record counts the twins placed at their compiled arm and the references refused, by file.

**Alternatives considered.** *Keep the references and tier them `syntactic`*: they are rust-analyzer's
answers in the wrong scope, not a syntactic read, so the tier would lie about what proves them. *Refuse only
the module-kind targets* (`self` → `aead`): the others resolve in the same wrong scope and are right only
when the two arms happen to name alike. *Read the build's features* stays the prevention (C-182).

**Built** (0.2.116-beta): `extract/rustsource.py` (the walk's `gates` chain, `RustFile.cfg_gates`,
`compiled_arms`), `extract/__init__.py` (lane B's definition lines in twin files, the refusal before the
join, the node's move before the twin arms are read, `_cfg_twin_record`'s two counts). Tests:
`test_shared_qualnames.py::TestTheCompiledArm` (gate spans, leaf's shape in small, the near misses, a live
`mod` around a dead `fn`, the fixture's ingest with lane B's facts hand-built both ways) and the `lane_b`
ingest on the host, uncached (`cow.width`'s node at the `not(alloc)` arm).

**Regrade** (`~/.hobbes/bench/c182-compiled-arm-2026-10-04/`: `regrade3.sh`, `cells.tsv`, `before-graphs/`,
`after/`; before is each cell's last standing report): **leaf 1,590 → 1,634 confirmed, 44 → 0
contradicted**, recall 86.9% → 89.3%, poison clean; 14 nodes moved, none added or removed; 45 references
refused in three files, each read against its arm (`crypto.rs`'s first `mod aead`, `proxy/mod.rs`'s
`#[cfg(windows)]` arm, `app/dns/client.rs`'s openssl and no-TLS arms), which took 23 `uses` edges' evidence
and split one `calls` pair at `proxy/mod.rs:348` to lane A's `syntactic` edge. memchr 921, dagger `sdk/rust`
3,595, rust_proj 17, sea-query 5,601, hecs 1,379, reshape 1,315: unchanged, 0 contradicted; memchr's,
sea-query's, hecs' and reshape's symbols and edges byte-identical (memchr's 3 and sea-query's 2 placed twins
already sat at their compiled arm).
