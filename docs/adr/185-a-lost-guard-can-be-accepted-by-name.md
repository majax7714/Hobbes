# ADR-185 — A lost guard can be accepted by name, and the review still says it

**Date:** 2026-10-29 · **Status:** accepted (Max, 2026-10-29: "register for now, we can tackle
independently later, add our own tests") · **Owner:** Max · **Source:** PR #6 (DEC-028, the TUI trim).

## Context

`hobbes review` fails when a module that a test reached on the base reaches none on the head (ADR-025's
coverage delta, `lost_guards`). That is the right default: a test deleted by accident is how a guard
disappears unnoticed.

DEC-028 deleted opencode's own tests in `tui/opencode/`, on purpose (Max chose the widest trim), and the
review of PR #6 listed 219 modules that lost every guard. Nothing could say "this was decided". On a pull
request the review would stay red. On `main` it reviews from the last green run (ADR-114), so after a
merge every later push would be red too, and the gate would stop meaning anything.

Those guards were also thin: opencode's tests were never in CI, and only the TUI's suite is run. Saying
the modules are unguarded is the true statement. What was missing was a way to record that the loss was
accepted, by whom, and why.

## Decision

1. **The record:** `.hobbes/accepted-lost-guards.yaml`, versioned with the repo's other review records,
   read from the working tree as the invariants are: it is a rule being applied, not part of the change
   under review. Each entry names its modules one by one (graph module ids, no patterns), with the
   `reason` and who `decided` it. A file that does not have that shape is refused, never half read.
2. **The review:** a lost guard whose module is on the list moves to its own list,
   `lost_guards_accepted`, and is printed under "lost every guarding test, accepted", grouped by reason,
   with every module named. It is not a reason for attention. A lost guard not on the list fails as
   before.
3. **Nothing else moves.** The graph, `tests.json` and `list_blind_spots` say what they said: these
   modules have no guarding test. The record changes only whether the review asks for one.
4. **Entries are removed when the modules get tests again.** An entry for a module that is guarded again,
   or no longer exists, matches nothing and is harmless. The record is kept short by deleting it then, not
   by a rule here.

## Consequences

- PR #6 can merge with its trim, and `main`'s review goes green after it.
- A later accidental loss in the same modules is caught only if the module had regained a guard and its
  entry was removed. While the entry stands, the module is accepted as unguarded: that is the cost, and
  it is why each module is named rather than a prefix.
- Adding our own tests for the fork's packages is open work (`docs/currently-open.md`).
- Version: the review says something new, so this is a patch (0.3.5-beta).

## Amendment, 2026-10-30: an accepted module is accepted whether its guard was lost or never there

**Status:** accepted (Max, 2026-10-30: "Accept by name", over a recorded review baseline or leaving it red).

The consequence above, "`main`'s review goes green after it", did not happen. On `main` the graph job
reviews from its last green run (ADR-114), `95edb94`, from before the watterson fold (ADR-181). From that
base every module of the fork is *new*, not lost, so a module on the list that no test reaches fell into
`new_unguarded`, which the list did not cover. The review of `95edb94..main` read 1,261 such modules on
this checkout and 1,292 in CI; 1,252 are the fork's, 9 this repo's own.

1. **A module on the list is accepted on either list.** A new module that no test reaches and that the
   record names moves to its own list, `new_unguarded_accepted`, printed under "new code no test reaches,
   accepted", grouped by reason, every module named. It is not a reason for attention. The record keeps
   its name (`accepted-lost-guards.yaml`): what it accepts is a module with no guarding test.
2. **One more entry**, for the fork's modules that no test reaches and that the trim's entry does not
   already name: opencode's code, vendored by the fold, whose own tests DEC-028 dropped or never had. Each
   is named, as before, and comes off when a test of ours reaches it.
3. **This repo's own modules are not accepted, but for a UI entry's render shell.** The nine get tests: six
   `hobbes.watterson` modules and `review/build`. The two UI entries, `review/src/main` and
   `tui/plugins/graph/tui`, have their logic moved into a module beside them with tests (`review/src/page.js`,
   `tui/plugins/graph/logic.ts`), as `review/src/graph.js` was; what is left renders, and is checked by eye
   (DEC-019), so each is named in an entry of its own with that reason (Max, 2026-10-30: "Extract logic,
   accept shells", over rendering them under jsdom and a Solid harness).
4. **CI installs `tui/opencode`'s Bun workspace in the graph job.** The 31 modules CI alone read as
   unguarded are reached through workspace packages (`@opencode/client`, `@opencode/theme`, …) that only an
   install links (ADR-186, C-198). Without it the CI review says less than the one on a checkout.

Nothing else moves: the graph and `list_blind_spots` still say these modules have no guarding test.
Version: the review says something new, a patch.
