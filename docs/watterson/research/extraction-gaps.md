# Extraction gaps seen from the environment

Gaps in Hobbes's extraction that limit what the environment can show
(graph views, DEC-014; permission checks, DEC-007). Kept here for now; the
user takes them to hobbes-public later (the user, 2026-10-16). Nothing here
is changed in this repo: `hobbes.extract` and `render.py` stay verbatim.

Measured on a lane-A ingest (`HOBBES_SCIP=0`) of a scratch clone of
`hobbes_public@2089e22`: 631 internal modules (601 module, 30 package), 181
externals, 10,022 symbols, 3,460 module edges, 20,685 symbol edges, 4,214
tests. Counts were re-checked except where marked.

| # | Gap | Evidence | Effect here |
|---|---|---|---|
| 1 | **Test fixtures are ingested as code.** Nothing marks a module as a fixture. | 169 of 631 modules sit under `tests/fixtures/` or `testdata/`. 7 of 15 `cli_entry_points` and the flask, fastapi and express routes in `interfaces.json` come from fixtures (survey count). | Graph views must drop them by path pattern; entry points and routes need the same filter. |
| 2 | **Links between languages are not extracted** (subprocess calls, HTTP clients, files handed between programs). | 0 import edges between the repo's top-level folders (`pipeline`, `go`, `web`, `bench`, …). | The top-level view of a multi-language repo is unconnected boxes. A map file can declare links in the meantime (DEC-014). |
| 3 | **argparse dispatch is not a call.** `set_defaults(func=…)` then `args.func(args)` leaves no edge. | `hobbes.cli.main` has one call edge, to `build_parser`. | Flow views (level 4) stop one hop after a Python CLI entry point; they note it for CLIs that import argparse. |
| 4 | **Route handlers often do not match a symbol id.** | 10 of 33 handlers match. Go handlers are named after the registering file's module (`go/internal/web/server.handleOverview`), while the symbol is `go/internal/web/artifacts.Server.handleOverview`; 5 handlers are empty (survey count; root cause unverified). | Flows from routes start at the one symbol with the handler's name in the registering folder, tagged "matched by name"; empty or shared names are cut. |
| 5 | **Go CLI entry targets are file paths**, not symbols (Python's are `mod:func`). | `interfaces.json` `cli_entry_points` (survey). | Flows take the file's only `main()`, tagged so. |
| 6 | **Externals do not say standard library or third party.** | `ext:bufio` and `ext:cytoscape` are both `{id, kind: external, name}`. | The system view cannot separate real dependencies from the standard library. |
| 7 | **`render.py` groups modules by splitting the id on `.`**, which only works for Python. Go, TS and C ids are paths without extensions. | `_group_key` in `render.py` (verbatim here, DEC-012). | `hobbes render` clusters non-Python modules poorly; the level model groups by `path` instead. |
| 8 | Dynamic dispatch in general: 5,245 of 8,813 functions have no incoming call edge (tests account for many). | Survey count. | Flow views will show "dispatch unknown" where a path breaks. |

Naming note: `graph.json`'s top-level `containment` key describes the lane B
sandbox (`extract/containment.py:1`), not code structure. Structure comes
from node `path`, `symbols[].module` and qualnames.
