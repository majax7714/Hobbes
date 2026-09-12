// Package clang turns clang's per-translation-unit JSON AST dumps into
// the oracle lane's edges.OracleExport (ADR-110, O9): C's resolution
// oracle, built on the front end scip-clang (C's lane B) itself uses.
//
// ReadDump reads one unit's dump as a token stream, never a whole-
// document unmarshal — a real dump is 25-35 MB, almost all system
// headers — into a Shard: the unit's own file, the in-repo files it
// loaded, its function declarations and definitions, and its in-repo
// call sites. Merge then joins every shard's declarations by name
// (javac's keyed merge, C's face of it) to resolve C's linkage rules
// and unions each site's targets across the shards that share it.
//
// The rules a Shard's sites and declarations follow (oracle-grading.md
// §7c):
//
//   - Sites: every CallExpr whose callee token lies in the repo. The
//     callee is peeled through ImplicitCastExpr, ParenExpr and a unary
//     `*`/`&`. What remains is either a DeclRefExpr naming a
//     FunctionDecl — a direct call, mode "static" — or anything else,
//     mode "dynamic" with no targets. A callee that is itself a call
//     (`get_fn()(2)`) is two sites: the inner call is recorded in its
//     own right (never dropped mid-peel) and the outer callee — the
//     value the inner call returns — is dynamic; a call nested anywhere
//     inside a callee expression gets the enclosing function as Caller,
//     never "".
//   - Positions: a plain clang location is itself. A macro-produced
//     position is a spelling/expansion pair; when the expansion is
//     itself a macro-argument expansion the position is the spelling
//     (the token as written), otherwise it is the expansion (the
//     invocation), mode "macro" for a site. The same rule positions a
//     definition, so a function a macro defines from a name argument
//     sits at the invocation that named it. clang's pseudo-buffers (a
//     "file" spelled "<scratch space>", "<built-in>" or "<command
//     line>": token pasting's synthetic result) are never files and
//     never enter Files; a chosen position that lies in one takes the
//     expansion instead, mode "macro" — this covers a callee spelled by
//     token pasting inside a macro argument (`ARGCALL(PASTE(do_,
//     one)())`), whose spelling is a pasted token with no real location.
//   - Identity: one site per (site path, line, column, spelling path,
//     line, column, mode, callee name) — a macro argument expanded
//     several times is one site; several different tokens sharing one
//     invocation's site position stay distinct sites; a unit compiled
//     twice, or a header several units load, adds nothing twice; targets
//     from several units at the same identity are unioned. Mode and
//     callee join the position pair because a callee that is itself a
//     call shares its (site, spelling) position with the call through
//     its result.
//   - Targets are definitions. Internal linkage (any declaration of the
//     name in the unit is storageClass "static") resolves to the unit's
//     own definition; with no definition in the unit, a static function
//     the unit declares or defines nowhere in the repo (a system
//     header's `static inline`, e.g. `__bswap_16`) is "external", and
//     one it declares in the repo but does not define is "undefined".
//     External linkage joins every shard's definitions of the name: one
//     distinct position is the target; several resolve to the calling
//     unit's own if it has one, else the site has no targets and counts
//     "link-ambiguous"; none, declared only outside the repo or only
//     implicitly (a builtin), is "external"; none, declared in the
//     repo, is "undefined". A site whose units resolve it to different
//     definitions keeps every target and counts "tu-split".
//
// The dumper omits a location's "file" and "line" when they repeat the
// previous location's, so the reader carries them forward across the
// whole document, in the order clang wrote it. An object whose first
// key is "offset" is a location; every other object, including
// "includedFrom", is not, and never moves that carried state.
package clang
