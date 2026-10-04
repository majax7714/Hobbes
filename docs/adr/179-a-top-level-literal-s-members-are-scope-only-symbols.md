# ADR-179 — A member of a literal bound at top level is a scope-only symbol

**Date:** 2026-10-04 · **Status:** accepted (Max, 2026-10-04: "recommended is approved", route 1b (a) "scope
only"); pre-registered before the build (`~/.hobbes/bench/ts-floor-2026-10-04/PREREG-1b.md`); **built**
(0.2.120-beta): the held-out draw took no cell (`RESULTS-1b.md`), and Max merged it on the fitted cells
(2026-10-04: "good to merge fitted cells with route a") · **Owner:** Max
· **Source:** C-176's floor; ADR-158 (whose amendment Max approved the same day); the step 0 in
`~/.hobbes/bench/ts-floor-2026-10-04/RESULTS-1b-step0.md`.

Narrows **C-176**. Draws no new edge.

## What is missing

ADR-158 files a TS/JS call under the innermost enclosing **graph symbol**. An object literal's method is not
one, so a call written inside it is filed under the **module**, as if written at top level. `who_calls` then
reads "module X calls f" for code that only runs when the method runs. On today's graphs the caller probe
(`c176-ts-scope/probe.py`, rows where Hobbes says the module and the tsc key a named function) counts ajv 458
such rows, tileserver-gl 43, hono 8, xmpp.js 6, cue 51 and kbet 17. Of these, the members of a literal bound
at top level hold ajv 449, tileserver-gl 43, hono 8, xmpp.js 6, cue 7 and kbet 2 (about 515). Most of ajv's are
its keyword definitions: `const def: CodeKeywordDefinition = { keyword: "…", code(cxt) { … } }`.

Step 0 also read what lane B writes for such members (scip-typescript in the image, `mini-literal/`):
- a member written `b: function () {}` or `c: () => …` gets a global `meta` symbol (`b0:`), which a call in
  another file names, and which the facts helper drops (ADR-027, Decision 3);
- a member written `a() {}`, an accessor, and a member of `export default {…}` get **local** symbols, so a
  call in another file is not named at all.

So a call **to** such a member is a different question from a call **within** one: the first is lane A's
alone for most members (`syntactic`), and about 48 key rows. The second needs only the syntax of where the
call is written. Max's route (a) takes the second only.

## Decision

1. **The members.** In a JS/TS file, a **direct** member of an object literal whose value runs as a function
   is a symbol of kind `method`, when the literal (through `as`, `satisfies` and parentheses) is bound at top
   level:

   | Binding | Qualname |
   |---|---|
   | `const`/`let`/`var X = {…}` at top level, `X` an identifier | `X.m` |
   | `module.exports = {…}` as a top-level statement | `module.exports.m` |
   | `exports.y = {…}` or `module.exports.y = {…}`, a top-level statement | `exports.y.m` / `module.exports.y.m` |
   | `export default {…}` | `default.m` |

   "Runs as a function" means a method (`m() {}`), a `get`/`set` accessor, or a property whose value is an
   arrow function or a function expression. Its name must be an identifier or a string literal; a computed
   name is not minted. A literal nested in the bound literal, and a literal that is returned, passed or
   assigned anywhere else, mints nothing (cue's 17 rows through a nested literal stay the module's).
2. **Fail toward drawing less.** A qualname minted twice in one file (a getter and its setter, two
   `module.exports = {…}`) and one equal to a symbol the file already has are both refused: none is minted,
   and their calls stay the module's.
3. **Scope only.** The symbol carries `scope_only: true`. It is a **caller** and never a **target**:
   - `enclosingScope` names it, so a call written in its body, or in a function nested in it, is filed under
     it (ADR-158's innermost-graph-symbol rule, with one more symbol in the vocabulary);
   - the join's enclosing lookup sees it, so a lane B fact inside it is filed under it too;
   - `starting_at` never answers with it. A lane B reference whose definition starts on its line (the
     one-line `const kw = { code() {} }`, where `kw.` is a kept `term`) claims nothing new. This is the
     inverse of ADR-129's mint, which is a target and not a scope;
   - `declQualname` does not name it, so lane A's fallback resolves nothing to it.
4. **What the tools say.** `who_calls` on such a symbol says first that calls *to* it are not drawn and why
   (C-176). C-156's value-only test does not count it as callable, since nothing can reach it: a module whose
   only callable symbols are scope-only stays value-only, in `testmap.value_only_modules` and its Go mirror.
5. Helper `HELPER_VERSION` 8 → 9: `symbols` gains a field and `scope` gains values.

## Predicted (pre-registered in `PREREG-1b.md`)

Grades cannot see this: no key reads a caller. So the predictions are that **nothing a key reads moves**,
and the caller probe moves exactly as step 0 says. On every keyed TS/JS cell: confirmed, contradicted,
recall and the poison check identical; the `(type, to, path, line)` multiset of `calls` and `uses` rows
identical, with only `from` changing, and only to a scope-only symbol; test reach and value-only modules
identical; no edge's `to` is scope-only; `below-floor` counts identical. On the probe: `wrong` and `dangling`
stay 0, and `lost-caller` falls by step 0's covered count. A held-out JS cell is drawn first (DRAW-RULE-2,
positions 42–80) and must hold at least 20 covered rows, or it is recorded as vacuous and the next is taken.

## Measured (2026-10-04; `RESULTS-1b.md`)

- **The held-out draw took no cell.** DRAW-RULE-2's walk from 42 to 80 met four candidates: flatlogic/
  react-material-admin (71) was taken by DRAW-RULE-2 and is vacuous here (2 `lost-caller` rows, both in a
  minified bundle); 75 and 78 thin or under-resolved; 76's install refused.
- **On the 13 fitted cells** Q1–Q5 and Q7 held: grades, the `(type, to, path, line)` rows, test reach,
  value-only modules, floored counts and every existing symbol identical; 171 scope-only symbols added;
  rows re-filed from the module to a member: ajv 628, tileserver-gl 59, hono 13, zod 11, cue 7, xmpp.js 6,
  kbet 2.
- **Q6 missed as worded.** `wrong` and `dangling` 0, and `lost-caller` fell by exactly step 0's count; but
  `agree`+`encloser` rose more than predicted (ajv +557 against 449, tileserver-gl +59 against 43): calls in an
  anonymous callback inside a member (`module-anon`) are now the member's (`encloser`), which the prediction
  did not count. None reads wrong.

## Not done

- **Calls to these members** (route 1b (b)): `syntactic` for shorthand members across files, `semantic`
  only where the helper keeps the `meta` symbol a property-function member gets. About 48 key rows.
- A literal nested in a bound literal, or returned, passed or assigned elsewhere; property-assigned
  and name-assigned functions (`X.prototype.y = function`; most of Preact's 247 and Express's 16 rows), unnamed
  classes and namespaces. C-176 keeps them.
