# ADR-164 — A Python call rooted at a standard-library import that no provider placed is tailed `stdlib-import`

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **R1** of three) and **built** (0.2.88-beta)
· **Owner:** Max · **Source:** flask's two single-repo rows (`~/.hobbes/bench/flask-rows-2026-10-02/RESULTS.md`,
row B), then this ADR's own step 0 and regrade (`~/.hobbes/bench/c181-stdlib-import/`).

Registers **C-181** (partial). Moves no edge: it renames the cause of sites already counted unresolved.
Precedent 1: the tools named the wrong cause for these sites.

## What is wrong

flask `app.py:15` imports `from urllib.parse import urlsplit`; `:725` calls it. scip-python 0.6.6 names
`urlsplit` with a symbol local to the document at both, so the call is neither resolved nor `external`.
The tail counted it `import-binding`, whose meaning says "usually a missing environment (C-23/C-27/C-30)".
The environment is not missing; the provider left the call unplaced. Written `parse.urlsplit(…)` or
`importlib.metadata.version(…)`, the same site counted `attr-call`, which blames C-2's untyped receiver;
the receiver is a module the file imports.

## Measured (step 0, in the image)

- **What gets a local symbol** (fixtures `fxc`, `fxd`, `fxe`; raw dumps beside them): every member of
  `urllib.parse`, `email.utils`, `importlib.metadata`, `concurrent.futures`, `urllib.request`,
  `xml.etree.ElementTree`, `http.client`, `json.decoder`, `logging.handlers` and `ctypes.wintypes`. That
  holds however the member is reached: `from a.b import x`, `from a import b` then `b.x`, `import a.b as c`
  then `c.x`, `import a.b` then `a.b.x`, or a function-local import. It also applies to `sys.exit` and
  `typing.overload`, from top-level modules, while `sys.getsizeof` resolves. gettext's `_` gets **no
  occurrence at all**. `os.path.join`, `functools.reduce`, `json.dumps` and `collections.abc.Mapping`
  resolve, and the brief's "a name landing in a top-level module is not affected" was wrong for `sys.exit`.
- **Lane A draws no edge to an in-repo namesake** at these sites. A fixture defined `urlsplit`, `exit`,
  `_` and `version` in the repo, and a repo module named `parse`; lane A drew nothing to any of them,
  whether lane B ran or not, because it binds only what the import names. One shape is the exception: a
  name that an `except ImportError:` branch rebinds to a repo function keeps lane A's `syntactic` edge
  there. Lane B's local answer cannot veto it the way an external one does (ADR-111). flask, click, rich
  and this repo write that shape 0 times. It is C-181's residual.
- **Probe** (`probe.py`, `probe.txt`: raw empty-environment indexes, syntax-only): the projected moves were
  flask 15, click 105 and rich 18 sites.

## The routes put to Max

- **R1 (recommended, chosen):** one Python tail class, `stdlib-import`, over any unresolved call whose name,
  or whose whole receiver, a stdlib import in the same file binds. Its meaning names the provider and the
  causes, it rolls up under *cannot resolve*, there is no refusal step, and a test pins lane A's abstention.
- **R2:** the brief's narrower rule: bare names from dotted stdlib modules only. It would leave the
  attribute forms, `sys.exit` and `_` under the wrong cause.
- **R3:** count the sites `external`. Not taken, because no provider placed them, and counting them would
  raise capture on a syntactic reading.

## The decision

1. **The bindings.** `tail.stdlib_bindings` reads lane A's own `PlainImport` and `FromImport` facts. A
   `from a.b import x as y` binds `y`, `import a.b as c` binds `c`, and `import a.b.c` binds the paths `a`,
   `a.b` and `a.b.c`. An import counts only when all of these hold:
   - it is absolute;
   - its module's top-level name is in the pinned `PY_STDLIB_MODULES` (Python 3.12's
     `sys.stdlib_module_names`, without underscored names);
   - that name is not a repo module's top-level name.

   A name that any other import in the file also binds is left out, because which one runs is not a fact
   the file states.
2. **The class.** It is decided after `fallback-resolved` and a scope-contained `local-binding`, and before
   `import-binding`, `builtin-name` and `attr-call`. It covers:
   - a bare call of a bound name;
   - an attribute call whose receiver, read from the call's own line, is exactly a bound name or path.

   A receiver that hangs off a call or a subscript (`f().sys.exit`), a longer chain (`sys.stdout.write`),
   and a receiver whose root is a parameter or a local in scope stay `attr-call`.
3. **Where a user meets it.** The tail's meaning names C-181, and also C-173 and C-178, because the
   regrade found those causes in the class too (below). The meaning appears in the ingest summary,
   `list_blind_spots`, the gate's reasons and the derived manifest's meanings.
4. **Python only** (`CLASSES_AVAILABLE`). Without lane B the class still holds: lane A resolves nothing
   outside the repo, and the meaning says so.

## Not taken

- **Requiring lane B's local symbol at the site.** The helper drops `local` occurrences by design. Carrying
  them would grow the facts schema to tell apart causes the class already names. The class records where
  the call is rooted, not which cause it was.
- **Refusing lane A's `except ImportError:` rebinding.** No graded cell writes it. It is registered as
  C-181's residual and pinned by the fixture's test, for Max to decide.

## Built (0.2.88-beta)

`extract/tail.py` (`PY_STDLIB_MODULES`, `stdlib_bindings`, `_receiver`, the class) is wired in
`extract/__init__.py`. The meanings are in `go/internal/knowledge/knowledge.go`, `derive/gate.py` and
`derive/manifests.py`. Tests: `test_tail.py::TestStdlibImport` (lane A and the tail), and
`test_stdlib_import_lane_b.py` on the `ministdlib` fixture (lane A alone, and `lane_b` on the host).

**Regrade:** the before arm is HEAD at `4c54a89`; `2a973cb` moved only Rust. The after arm is this build.
`run.sh`, `compare.py` and `compare.txt` are in `~/.hobbes/bench/c181-stdlib-import/`. Edges and symbols
are byte-identical on every cell, and so are the grade lines.

| cell | confirmed | suspect | `stdlib-import` | from `attr-call` | from `import-binding` | probe projected |
|---|---:|---:|---:|---:|---:|---:|
| flask | 1,552 → 1,552 | 15 → 15 | 0 → 34 | −30 | −4 | 15 |
| click | 3,768 → 3,768 | 20 → 20 | 0 → 181 | −80 | −101 | 105 |
| rich | 4,968 → 4,968 | 42 → 42 | 0 → 82 | −65 | −17 | 18 |
| pyparsing (standing driver) | 3,517 → 3,517 | 66 → 66 | 0 → 27 | −10 | −17 | — |

These are trace-graded cells: they measure recall, never precision (C-60), and a trace key never
contradicts.

**Why the measured moves exceed the projection.** The probe read raw indexes taken without the staged
`pyrightconfig.json`, and it did not count decorators as calls. `sites.py` and `causes.py` attribute each
moved site from the ingest's own facts:

| cell | C-181 local symbol | C-181 `_` | no answer in code Pyright reads as dead (C-173) | C-178 star re-export misnames | total |
|---|---:|---:|---:|---:|---:|
| flask | 33 (18 of them `@t.overload`) | 0 | 0 | 1 | 34 |
| click | 71 | 74 | 31 | 5 | 181 |
| rich | 22 | 0 | 58 | 2 | 82 |

**A gap this measurement found, outside this ADR.** rich's `_win32_console.py` raises `ImportError` in the
`else` of a `sys.platform == "win32"` test. Pyright reads everything after it as dead, and the ingest's facts
hold no lane B answer from line 22 to line 577. C-173's record for the file names line 12 only. It is
noted in `currently-open.md`.
