# Oracle cell — cypress-io/github-action, zone `.`, 2026-09-20 — the first JavaScript cell graded with its dependency tree (C-165)

Repo: https://github.com/cypress-io/github-action, shallow clone at `~/.hobbes/bench/js-cells/repos/cypress-io__github-action`, commit `01e3b659a495` (fixed for this cell). **Drawn at random** (§10.24): ADR-140's pool and order (`random.Random(20260919)`), the walk resumed at position 7 with two criteria added and stated first (`~/.hobbes/bench/js-cells/c165/DRAW-RULE.md`): a lockfile the ingest provisions from, and a non-empty `dependencies`. Positions 7–21 walked, each pass-over recorded with its reason (`c165/draw-log.md`); two candidates were refused by the ingest's own `npm ci --ignore-scripts` and the next taken — 9 `hack-chat/main` (`uwuify-1.0.1.tgz` 404, unpublished) and 11 `maptiler/tileserver-gl` (lockfile out of sync with its manifest, xmpp.js's case). A GitHub Action: one 1,048-line `index.js`, `src/`, and 26 example packages; 77 JavaScript files, one zone, a thin cell (76 `calls` edges at 154 sites). Hobbes 0.2.57-beta @ `3df2ed1`; lane B contained (`HOBBES_SCIP=1`); the ingest provisioned 177 packages from the root `package-lock.json` (`~/.hobbes/cache/npm/5f31b8be7cf816e8`), and the oracle ran over the clone with that same tree mounted at `node_modules`, in the image with no network; tsc 5.9.3, the harness's, `--no-tsconfig` (ADR-140 step 3). The dirty tree is the ingest's `.gitignore` line (ADR-012).

**Graded twice, same sha, same code** (pre-registered): *provisioned* (the tree on both sides) and *withheld* (a clone with `package-lock.json` removed, so the ingest declines the install — C-34 — and the oracle gets no tree: the state of Express, Preact and xmpp.js). Command: `~/.hobbes/bench/js-cells/grade.sh c165-provisioned <clone> <clone> <tree>` and `grade.sh c165-withheld <copy> <copy>`. Outputs in `~/.hobbes/bench/js-cells/cells/c165-{provisioned,withheld}/`; the run's record is `c165/RESULTS.md`.

## Numbers — withheld (report.txt, verbatim)

```
cell .  oracle tsc 5.9.3 (harness; no tsconfig — the ingest's generated options) (resolution)  sha 01e3b659
hobbes edges 154: confirmed 154  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (154/154)
recall 89.0% (154/173 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 173; misses map[func-value→local-binding:4 func-value→parameter:3 static→closure:4 static→variable:8]
recall-collapsed 89.0% (154/173 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[func-value→local-binding]   0.0% (0/4)  misses 4 = 21.1% of all misses
  recall[func-value→parameter]   0.0% (0/3)  misses 3 = 15.8% of all misses
  recall[func-value→variable] 100.0% (86/86)  misses 0 = 0.0% of all misses
  recall[static→closure    ]   0.0% (0/4)  misses 4 = 21.1% of all misses
  recall[static→function   ] 100.0% (8/8)  misses 0 = 0.0% of all misses
  recall[static→variable   ]  88.2% (60/68)  misses 8 = 42.1% of all misses
  tier semantic   confirmed 154  contradicted 0  abstract 0  silent 0
  line-grain tolerance used on 17 edge(s) (several oracle sites on one line)
  missed       examples/browser/cypress.config.js:23  setupNodeEvents -> examples/browser/cypress.config.js:8 (on) [func-value→parameter]
  missed       examples/browser/cypress.config.js:9  setupNodeEvents -> examples/browser/cypress.config.js:8 (on) [func-value→parameter]
  missed       examples/component-tests/src/App.jsx:21  <anonymous> -> examples/component-tests/src/App.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:11  handleIncrement -> examples/component-tests/src/components/Stepper.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:12  handleIncrement -> examples/component-tests/src/components/Stepper.jsx:5 (onChange) [static→closure]
  missed       examples/component-tests/src/components/Stepper.jsx:17  handleDecrement -> examples/component-tests/src/components/Stepper.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:18  handleDecrement -> examples/component-tests/src/components/Stepper.jsx:5 (onChange) [static→closure]
  missed       examples/quiet/cypress.config.js:8  setupNodeEvents -> examples/quiet/cypress.config.js:7 (on) [func-value→parameter]
  missed       examples/wait-on-vite/counter.js:7  <anonymous> -> examples/wait-on-vite/counter.js:3 (setCounter) [static→closure]
  missed       examples/wait-on-vite/counter.js:8  setupCounter -> examples/wait-on-vite/counter.js:3 (setCounter) [static→closure]
  missed       index.js:636  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:641  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:646  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:651  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:656  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:661  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:668  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:683  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       src/ping.js:35  ping -> src/ping.js:14 (got) [func-value→local-binding]
poison check: PASS — 154 seeded wrong edges: 146 refused, 8 unjudged (oracle silent there), 0 falsely confirmed
```

## Numbers — provisioned, the cell's standing grade (report.txt, verbatim)

```
cell .  oracle tsc 5.9.3 (harness; no tsconfig — the ingest's generated options) (resolution)  sha 01e3b659
hobbes edges 154: confirmed 154  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (154/154)
recall 89.0% (154/173 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 413; misses map[func-value→local-binding:4 func-value→parameter:3 static→closure:4 static→variable:8]
recall-collapsed 89.0% (154/173 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[func-value→local-binding]   0.0% (0/4)  misses 4 = 21.1% of all misses
  recall[func-value→parameter]   0.0% (0/3)  misses 3 = 15.8% of all misses
  recall[func-value→variable] 100.0% (86/86)  misses 0 = 0.0% of all misses
  recall[static→closure    ]   0.0% (0/4)  misses 4 = 21.1% of all misses
  recall[static→function   ] 100.0% (8/8)  misses 0 = 0.0% of all misses
  recall[static→variable   ]  88.2% (60/68)  misses 8 = 42.1% of all misses
  tier semantic   confirmed 154  contradicted 0  abstract 0  silent 0
  line-grain tolerance used on 17 edge(s) (several oracle sites on one line)
  missed       examples/browser/cypress.config.js:23  setupNodeEvents -> examples/browser/cypress.config.js:8 (on) [func-value→parameter]
  missed       examples/browser/cypress.config.js:9  setupNodeEvents -> examples/browser/cypress.config.js:8 (on) [func-value→parameter]
  missed       examples/component-tests/src/App.jsx:21  <anonymous> -> examples/component-tests/src/App.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:11  handleIncrement -> examples/component-tests/src/components/Stepper.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:12  handleIncrement -> examples/component-tests/src/components/Stepper.jsx:5 (onChange) [static→closure]
  missed       examples/component-tests/src/components/Stepper.jsx:17  handleDecrement -> examples/component-tests/src/components/Stepper.jsx:7 (setCount) [func-value→local-binding]
  missed       examples/component-tests/src/components/Stepper.jsx:18  handleDecrement -> examples/component-tests/src/components/Stepper.jsx:5 (onChange) [static→closure]
  missed       examples/quiet/cypress.config.js:8  setupNodeEvents -> examples/quiet/cypress.config.js:7 (on) [func-value→parameter]
  missed       examples/wait-on-vite/counter.js:7  <anonymous> -> examples/wait-on-vite/counter.js:3 (setCounter) [static→closure]
  missed       examples/wait-on-vite/counter.js:8  setupCounter -> examples/wait-on-vite/counter.js:3 (setCounter) [static→closure]
  missed       index.js:636  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:641  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:646  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:651  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:656  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:661  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:668  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       index.js:683  runTestsUsingCommandLine -> index.js:62 (quoteWindowsArgument) [static→variable]
  missed       src/ping.js:35  ping -> src/ping.js:14 (got) [func-value→local-binding]
poison check: PASS — 154 seeded wrong edges: 148 refused, 6 unjudged (oracle silent there), 0 falsely confirmed
```

## Triage

0 contradicted in either arm. **The two arms' graded rows are identical, row for row, and so is the graph** (110 nodes, 86 module edges, 76 `calls` + 42 `uses`, every symbol edge's target in the repo). What the tree changed is the key's side and the environment number: external oracle pairs 173 → 413 (+240), `dependency_coverage` 0 of 22 → 14 of 22 declared packages resolved by the index, and the poison check judged two more seeded rows (146 → 148 refused).

**No row grades a call into a package, because Hobbes draws none.** Its statement about a third-party package, in either arm, is the module-level `imports → ext:<pkg>` edge (77 here, syntactic, identical between the arms); no `calls` or `uses` edge targets a declaration under `node_modules`. The same holds on the TypeScript cells that have a tree (cheerio, zod, hono: 0 graded rows with a `node_modules` target). The key's 413 external pairs therefore have no Hobbes counterpart to confirm or contradict — C-165, corrected to that wording at 0.2.58-beta.

Misses, 19, all C-58's shapes: `static→variable` 8, `func-value→local-binding` 4, `static→closure` 4, `func-value→parameter` 3.
