// Package clang turns clang's per-translation-unit JSON AST dumps into
// the oracle lane's edges.OracleExport (ADR-110, O9; ADR-113, O10): C's
// and C++'s resolution oracle, built on the front end scip-clang (their
// lane B) itself uses.
//
// ReadDump reads one unit's dump as a token stream, never a whole-
// document unmarshal — a real dump is 25-35 MB, almost all system
// headers — into a Shard: the unit's own file, the in-repo files it
// loaded, its function declarations and definitions, and its in-repo
// call sites. Merge then joins every shard's declarations by key
// (javac's keyed merge, C's and C++'s face of it) to resolve C's linkage
// rules and unions each site's targets across the shards that share it.
// A unit's language is its own: an entry whose file is .cpp, .cc, .cxx,
// .C or .c++ runs clang++, and every other entry runs clang, whatever
// language the cell names — a mixed build root is one root.
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
//
// # C++
//
// C++'s rules (ADR-113 §3) extend the above; everything this section
// does not name is C's, unchanged — the peeling, the positions, the
// macro rule, the identity rule, and targets-are-definitions.
//
//   - Declarations are FunctionDecl and C++'s four member shapes
//     (CXXMethodDecl, CXXConstructorDecl, CXXDestructorDecl,
//     CXXConversionDecl), each carrying its mangled name, whether it was
//     written virtual, its class and its signature. A FunctionTemplateDecl
//     is not a declaration: the FunctionDecls inside it — the pattern and
//     each specialisation — are, all at the template's own line, as the
//     dump gives them. A declaration node written without a location is a
//     stub for one written in full elsewhere (an overload candidate under
//     an UnresolvedLookupExpr, operator new under a CXXNewExpr) and
//     declares nothing. A site inside a method is attributed to
//     Class::name, the class being the enclosing record or, for an
//     out-of-line definition, the one parentDeclContextId names.
//   - Sites. A CallExpr is C's, and its DeclRefExpr may now name a
//     CXXMethodDecl — a static or qualified member call, mode "static".
//     A CXXMemberCallExpr's callee is the MemberExpr under the same
//     peeling, which names its method by id rather than by a
//     referencedDecl: mode "static", or "virtual" where that declaration
//     was written virtual. clang prints the keyword only where the source
//     does, so an override that omits it reads as an ordinary member
//     call; the target is the same method either way. A
//     CXXOperatorCallExpr peels as a CallExpr's and is mode "operator".
//     A CXXConstructExpr — and its CXXTemporaryObjectExpr subclass, and
//     the one inside a CXXNewExpr, the `new` itself being no site — has
//     no callee at all: it sits at its own range begin, mode
//     "constructor", and its target is the constructor of its own class
//     whose signature is the ctorType clang printed. A callee that names
//     no declaration stays dynamic, whatever the node: a template
//     pattern's dependent operator is an unresolved lookup, not a call to
//     something.
//   - Targets. An isImplicit constructor or destructor is never a target
//     and the site that would name one is dropped: no source line calls a
//     compiler-written member. A virtual site's target is the declared
//     method — the front end names the static type's, and no class
//     hierarchy is built over it (an override Hobbes drew instead is a
//     contradiction to measure, not to excuse). Target.Kind carries what
//     the declaration is: function, method, constructor or destructor.
//   - The join key is the mangled name where a declaration has one —
//     unique per entity, so overloads and a template's specialisations
//     are told apart — and C's name otherwise (`extern "C"`, `main`). In
//     C the two are the same string. Internal linkage is a free
//     function's own storageClass "static" or any declaration inside an
//     unnamed namespace, resolved unit-local as C's statics are; a member
//     function's storageClass "static" is not internal linkage, and its
//     calls join across units like any other name.
//   - Coverage counts sites_virtual, sites_operator and sites_constructor
//     beside C's sites_static, sites_macro, sites_dynamic,
//     sites_external, sites_link_ambiguous, sites_undefined and
//     sites_tu_split, and units_cpp — the units that really ran under
//     clang++ — beside units and units_failed; a cell run as `--lang cpp`
//     also records lang_cpp, its own claim, which a root with no C++ unit
//     does not contradict.
package clang
