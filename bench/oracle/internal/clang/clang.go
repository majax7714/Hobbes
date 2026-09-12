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
//     mode "dynamic" with no targets.
//   - Positions: a plain clang location is itself. A macro-produced
//     position is a spelling/expansion pair; when the expansion is
//     itself a macro-argument expansion the position is the spelling
//     (the token as written), otherwise it is the expansion (the
//     invocation), mode "macro" for a site. The same rule positions a
//     definition, so a function a macro defines from a name argument
//     sits at the invocation that named it.
//   - Identity: one site per (site path, line, column, spelling path,
//     line, column) — a macro argument expanded several times is one
//     site; several different tokens sharing one invocation's site
//     position stay distinct sites; a unit compiled twice, or a header
//     several units load, adds nothing twice; targets from several
//     units at the same identity are unioned.
//   - Targets are definitions. Internal linkage (any declaration of the
//     name in the unit is storageClass "static") resolves to the unit's
//     own definition. External linkage joins every shard's definitions
//     of the name: one distinct position is the target; several resolve
//     to the calling unit's own if it has one, else the site has no
//     targets and counts "link-ambiguous"; none, declared only outside
//     the repo or only implicitly (a builtin), is "external"; none,
//     declared in the repo, is "undefined". A site whose units resolve
//     it to different definitions keeps every target and counts
//     "tu-split".
//
// The dumper omits a location's "file" and "line" when they repeat the
// previous location's, so the reader carries them forward across the
// whole document, in the order clang wrote it. An object whose first
// key is "offset" is a location; every other object, including
// "includedFrom", is not, and never moves that carried state.
package clang
