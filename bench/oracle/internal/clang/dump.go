package clang

import (
	"encoding/json"
	"fmt"
	"io"
	"path/filepath"
	"sort"
	"strings"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// rawPos is one resolved clang location. Pseudo marks a clang
// pseudo-buffer (a "file" spelled "<scratch space>", "<built-in>" or
// "<command line>"): never in the repo, and never a location a chosen
// position may keep (resolve redirects away from one).
type rawPos struct {
	Path   string
	InRepo bool
	Pseudo bool
	Line   int
	Col    int
}

// pos is a "loc" or "range"."begin" field's value: either a plain
// location, or a clang macro spelling/expansion pair.
type pos struct {
	macro        bool
	plain        rawPos
	spelling     rawPos
	expansion    rawPos
	argExpansion bool
}

// resolve returns the position ADR-110's rule assigns a plain or macro
// position, and whether it was written in a macro's body (mode
// "macro") rather than at a plain call or a macro argument. A chosen
// position that lies in a pseudo-buffer (token pasting's synthetic
// result, e.g. a macro argument that names a pasted-together callee)
// is never usable: the rule falls back to the expansion, mode "macro".
func (p pos) resolve() (rawPos, bool) {
	if !p.macro {
		return p.plain, false
	}
	chosen, macroMode := p.expansion, true
	if p.argExpansion {
		chosen, macroMode = p.spelling, false
	}
	if chosen.Pseudo {
		chosen, macroMode = p.expansion, true
	}
	return chosen, macroMode
}

// spellingPos is the position ADR-110's site identity keys on: always
// the spelling, even when resolve reports the expansion.
func (p pos) spellingPos() rawPos {
	if !p.macro {
		return p.plain
	}
	return p.spelling
}

// qualifierFromMacroBody is H-31's shape (ADR-113 §3): a callee whose
// range begins in a macro's body — the `::` of `#define SYS(call)
// ::call`, fmt's FMT_SYSTEM — and ends at the name the macro's argument
// supplied. The begin is then a position nobody wrote the call on (the
// `#define`'s own line, in fmt another file altogether); the end is the
// author's own token, and the site is the end's.
//
// The flags alone cannot say it: a nested expansion prints only its
// outermost spelling/expansion pair, so where the invocation is itself
// a macro's argument the body token carries isMacroArgExpansion exactly
// as the author's own token does. What separates them is where they are
// spelled — a body token on the `#define`'s line, the author's at the
// use site — so a plain qualified call written inside a macro argument
// (`RETRY(ns::h(1))`, both ends spelled at the use site) keeps its
// qualifier's column, as an unwrapped `ns::h(1)` does.
func qualifierFromMacroBody(begin, end pos) bool {
	if !begin.macro || !end.macro || !end.argExpansion {
		return false
	}
	if begin.spelling == begin.expansion {
		return false
	}
	return begin.spelling.Path != end.spelling.Path || begin.spelling.Line != end.spelling.Line
}

// reader is a single left-to-right pass over one dump's JSON tokens,
// carrying the location state the dumper's omissions rely on (file and
// line repeat forward until a location spells them again) and the
// enclosing function's name for Caller attribution.
type reader struct {
	dec  *json.Decoder
	dir  string
	repo string

	curPath   string
	curInRepo bool
	curPseudo bool
	curLine   int

	// curClass is the enclosing C++ record's name (a method's Caller
	// qualifier and a constructor's class); curAnon marks an unnamed
	// namespace's subtree, whose declarations link internally the way
	// C's statics do.
	curClass string
	curAnon  bool

	// uneval is the depth of enclosing unevaluated operands: a `sizeof`
	// or `alignof` argument, a `noexcept` expression's operand, a
	// requires-expression's requirements (ADR-121 §3). The subtree is
	// still walked — a lambda or a local class inside one declares — but
	// no site it holds is recorded, because no instruction makes that
	// call. unevaluated counts what that drops, one per call or
	// construct, for the coverage line.
	uneval      int
	unevaluated int

	mainFile string
	files    map[string]bool
	decls    []Decl
	calls    []Call
	// declByID indexes decls by clang node id and records maps a
	// CXXRecordDecl's id to its name: C++ names a callee by id (a member
	// call's referencedMemberDecl, a DeclRefExpr's referencedDecl) and an
	// out-of-line definition names its class by parentDeclContextId.
	declByID map[string]int
	records  map[string]string
	pending  []pendingCall
}

// pendingCall is a site whose callee the walk cannot name where it
// stands: a call naming a declaration by id, which a class's own body
// may reach before the dump declares it, or a construct expression,
// which names no callee at all. finish names both.
type pendingCall struct {
	idx    int
	declID string
	member bool
	// class and ctorType name a construct expression's target: the
	// record's own name and the constructor signature clang printed.
	class    string
	ctorType string
}

// ReadDump reads one translation unit's clang AST dump (`clang
// -fsyntax-only -Xclang -ast-dump=json`): a stream of JSON tokens read
// in document order, never a whole-document unmarshal — a real dump is
// 25-35 MB, almost all system headers. dir is the compile entry's own
// directory; repo is the repository root, both absolute. An
// unparseable dump returns an error, never a partial shard.
func ReadDump(r io.Reader, dir, repo string) (*Shard, error) {
	rd := &reader{dec: json.NewDecoder(r), dir: dir, repo: repo, files: map[string]bool{},
		declByID: map[string]int{}, records: map[string]string{}}
	if _, err := rd.walkNode(""); err != nil {
		return nil, fmt.Errorf("clang: %w", err)
	}
	rd.finish()
	s := &Shard{File: rd.mainFile, Decls: rd.decls, Calls: rd.calls, Unevaluated: rd.unevaluated}
	for f := range rd.files {
		s.Files = append(s.Files, f)
	}
	sort.Strings(s.Files)
	if s.Files == nil {
		s.Files = []string{}
	}
	if s.Decls == nil {
		s.Decls = []Decl{}
	}
	if s.Calls == nil {
		s.Calls = []Call{}
	}
	return s, nil
}

// normalize resolves a clang-spelled file (relative to dir, or
// absolute) to a repo-relative path, reporting false when it lies
// outside repo.
func normalize(raw, dir, repo string) (string, bool) {
	if raw == "" {
		return "", false
	}
	var abs string
	if filepath.IsAbs(raw) {
		abs = filepath.Clean(raw)
	} else {
		abs = filepath.Clean(filepath.Join(dir, raw))
	}
	rel, err := filepath.Rel(repo, abs)
	if err != nil {
		return "", false
	}
	rel = filepath.ToSlash(rel)
	if rel == ".." || strings.HasPrefix(rel, "../") {
		return "", false
	}
	return rel, true
}

// isPseudoFile reports whether a clang-spelled file is one of its
// pseudo-buffers ("<scratch space>", "<built-in>", "<command line>"):
// synthetic locations that are never in the repo and never a real file.
func isPseudoFile(raw string) bool {
	return strings.HasPrefix(raw, "<")
}

// walkNode decodes one AST node value (its opening '{' not yet
// consumed), recording declarations and in-repo call sites as it goes,
// and returns the node's own "kind" so a declaration's own walk can
// notice a direct CompoundStmt child (a definition). fn is the name of
// the nearest enclosing function or method (Caller); "" at the top.
func (rd *reader) walkNode(fn string) (string, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return "", err
	}
	var kind, id, name, storageClass, mangled, parentID, qualType, ctorType string
	var isImplicit, isVirtual, hasLoc bool
	var nodeLoc, nodeRange pos
	hasCompound := false

	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return "", err
		}
		switch key {
		case "kind":
			if kind, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "id":
			if id, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "name":
			if name, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "storageClass":
			if storageClass, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "mangledName":
			if mangled, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "parentDeclContextId":
			if parentID, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "isImplicit":
			if isImplicit, err = nextBool(rd.dec); err != nil {
				return "", err
			}
		case "virtual":
			if isVirtual, err = nextBool(rd.dec); err != nil {
				return "", err
			}
		case "type":
			if qualType, err = rd.readQualType(); err != nil {
				return "", err
			}
		case "ctorType":
			if ctorType, err = rd.readQualType(); err != nil {
				return "", err
			}
		case "loc":
			hasLoc = true
			if nodeLoc, err = rd.readPos(); err != nil {
				return "", err
			}
		case "range":
			// A construct site sits at its node's range begin: it names no
			// callee whose own token could position it.
			if nodeRange, _, err = rd.readRange(); err != nil {
				return "", err
			}
		case "inner":
			if isCallKind(kind) {
				if err = rd.walkCallInner(fn, kind); err != nil {
					return "", err
				}
				continue
			}
			childFn, childClass, childAnon := fn, rd.curClass, rd.curAnon
			if isDeclKind(kind) {
				childFn = qualify(rd.classOf(parentID), name)
			}
			if kind == "CXXRecordDecl" && name != "" {
				childClass = name
			}
			if kind == "NamespaceDecl" && name == "" {
				childAnon = true
			}
			outerClass, outerAnon := rd.curClass, rd.curAnon
			rd.curClass, rd.curAnon = childClass, childAnon
			if isUnevaluatedKind(kind) {
				rd.uneval++
			}
			hasCompound, err = rd.walkChildren(kind, childFn)
			if isUnevaluatedKind(kind) {
				rd.uneval--
			}
			rd.curClass, rd.curAnon = outerClass, outerAnon
			if err != nil {
				return "", err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return "", err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return "", err
	}

	switch {
	case kind == "CXXRecordDecl":
		if id != "" && name != "" {
			rd.records[id] = name
		}
	case isDeclKind(kind) && hasLoc:
		// A declaration node the dump writes without a location is a stub
		// standing for one written elsewhere (an overload candidate under
		// an UnresolvedLookupExpr, operator new under a CXXNewExpr): it
		// declares nothing, and must not shadow the real node's id.
		p, _ := nodeLoc.resolve()
		if id != "" {
			rd.declByID[id] = len(rd.decls)
		}
		rd.decls = append(rd.decls, Decl{
			Name: name, Mangled: mangled, Kind: declKind(kind), Class: rd.classOf(parentID),
			Type: qualType, Virtual: isVirtual, Body: hasCompound,
			Static:   rd.curAnon || (kind == "FunctionDecl" && storageClass == "static"),
			Implicit: isImplicit, InRepo: p.InRepo,
			Pos: edges.Pos{Path: p.Path, Line: p.Line},
		})
	case isConstructKind(kind):
		rd.recordConstruct(nodeRange, fn, qualType, ctorType)
	}
	return kind, nil
}

// walkChildren decodes an "inner" array of ordinary AST node children
// (every kind but a call, whose callee needs peeling — walkCallInner
// handles those). It reports whether any direct child is a CompoundStmt,
// so its declaring caller can tell a definition from a bare declaration.
func (rd *reader) walkChildren(parentKind, fn string) (bool, error) {
	if err := expectDelim(rd.dec, '['); err != nil {
		return false, err
	}
	hasCompound := false
	for rd.dec.More() {
		kind, err := rd.walkNode(fn)
		if err != nil {
			return false, err
		}
		if isDeclKind(parentKind) && kind == "CompoundStmt" {
			hasCompound = true
		}
	}
	if err := expectDelim(rd.dec, ']'); err != nil {
		return false, err
	}
	return hasCompound, nil
}

// walkCallInner decodes a call node's "inner" array — a CallExpr, a
// CXXMemberCallExpr and a CXXOperatorCallExpr all write their callee
// first: it is peeled to a mode and position, and the rest are ordinary
// children (a call's arguments can hold further calls).
func (rd *reader) walkCallInner(fn, siteKind string) error {
	if err := expectDelim(rd.dec, '['); err != nil {
		return err
	}
	first := true
	for rd.dec.More() {
		if first {
			cr, err := rd.peelCallee(fn)
			if err != nil {
				return err
			}
			rd.record(cr, fn, siteKind)
		} else if _, err := rd.walkNode(fn); err != nil {
			return err
		}
		first = false
	}
	return expectDelim(rd.dec, ']')
}

// record appends the site a peeled callee makes, if any, and queues it
// for finish when it names a declaration by id. A call standing inside
// an unevaluated operand makes no site: the callee has already been
// peeled where it stands (nothing is consumed unrecorded), and the site
// it would have made is counted instead.
func (rd *reader) record(cr calleeResult, fn, siteKind string) {
	c := rd.buildCall(cr, fn, siteKind)
	if c == nil {
		return
	}
	if rd.uneval > 0 {
		rd.unevaluated++
		return
	}
	rd.calls = append(rd.calls, *c)
	if c.Mode != "dynamic" && cr.declID != "" {
		rd.pending = append(rd.pending, pendingCall{idx: len(rd.calls) - 1, declID: cr.declID, member: cr.isMember})
	}
}

// buildCall turns a peeled callee into a Call, or nil when its site
// does not lie in the repo (rule: only in-repo call sites are sites at
// all). The callee's name is provisional: finish replaces it with the
// declaration's own key once the whole dump is read.
func (rd *reader) buildCall(cr calleeResult, fn, siteKind string) *Call {
	// A MemberExpr callee names a function only under a member call: the
	// same shape under a plain CallExpr is a call through a member of
	// function-pointer type, which stays dynamic and keeps the whole
	// expression's position (C's shape, ADR-110). A member call takes the
	// member's own token instead, position and spelling both (H-28).
	memberCall := cr.isMember && siteKind == "CXXMemberCallExpr"
	at := cr.pos
	switch {
	case memberCall:
		at = cr.memberPos
	// A macro body supplied the qualifier and the argument the name: the
	// range end is the only position the author wrote (H-31).
	case qualifierFromMacroBody(cr.pos, cr.endPos):
		at = cr.endPos
	}
	sitePos, macroBody := at.resolve()
	if !sitePos.InRepo {
		return nil
	}
	spell := at.spellingPos()
	mode, callee := "dynamic", ""
	if cr.isFunc && (!cr.isMember || memberCall) {
		callee = cr.name
		switch {
		case siteKind == "CXXOperatorCallExpr":
			mode = "operator"
		case siteKind == "CXXMemberCallExpr":
			mode = "static"
		case macroBody:
			mode = "macro"
		default:
			mode = "static"
		}
	}
	return &Call{
		Site:     edges.Pos{Path: sitePos.Path, Line: sitePos.Line},
		Col:      sitePos.Col,
		Spell:    edges.Pos{Path: spell.Path, Line: spell.Line},
		SpellCol: spell.Col,
		Caller:   fn,
		Mode:     mode,
		Callee:   callee,
	}
}

// recordConstruct records a CXXConstructExpr (and its
// CXXTemporaryObjectExpr subclass) as a site: the node carries no callee
// at all, so it sits at its own range begin, mode "constructor", and
// finish names the constructor of its own class whose signature is the
// ctorType clang printed.
func (rd *reader) recordConstruct(p pos, fn, qualType, ctorType string) {
	sitePos, _ := p.resolve()
	if !sitePos.InRepo {
		return
	}
	// A construction inside an unevaluated operand — `sizeof(Circle(1))`
	// — is the call rule's other face: no object is built, so it is
	// dropped and counted, its class never named.
	if rd.uneval > 0 {
		rd.unevaluated++
		return
	}
	spell := p.spellingPos()
	rd.calls = append(rd.calls, Call{
		Site:     edges.Pos{Path: sitePos.Path, Line: sitePos.Line},
		Col:      sitePos.Col,
		Spell:    edges.Pos{Path: spell.Path, Line: spell.Line},
		SpellCol: spell.Col,
		Caller:   fn,
		Mode:     "constructor",
	})
	rd.pending = append(rd.pending, pendingCall{idx: len(rd.calls) - 1, class: className(qualType), ctorType: ctorType})
}

// finish names every queued site's callee once the whole dump is read: a
// member call's declaration may stand below the body that calls it, and
// a construct expression names none at all. A site that resolves to a
// compiler-written constructor or destructor (isImplicit) is dropped —
// no source line calls it — and so is a construct expression whose unit
// declares no constructor of that signature.
func (rd *reader) finish() {
	ctors := map[string][]int{}
	for i, d := range rd.decls {
		if d.Kind == "constructor" {
			k := d.Class + "\x00" + d.Type
			ctors[k] = append(ctors[k], i)
		}
	}
	dropped := map[int]bool{}
	for _, p := range rd.pending {
		d := rd.pendingDecl(p, ctors)
		if d == nil {
			if p.declID == "" {
				dropped[p.idx] = true
			}
			continue
		}
		if d.Implicit && (d.Kind == "constructor" || d.Kind == "destructor") {
			dropped[p.idx] = true
			continue
		}
		c := &rd.calls[p.idx]
		// The site's key is the declaration's own, spelled the one way
		// Merge joins by; CalleeName stays the name as written.
		c.Callee, c.CalleeName = declKey(*d), d.Name
		if p.member && d.Virtual {
			c.Mode = "virtual"
		}
	}
	if len(dropped) == 0 {
		return
	}
	kept := rd.calls[:0]
	for i, c := range rd.calls {
		if !dropped[i] {
			kept = append(kept, c)
		}
	}
	rd.calls = kept
}

// pendingDecl is the declaration a queued site names: the one its id
// indexes, or — for a construct expression — the first constructor of
// its class carrying that signature (a unit that both declares and
// defines one keeps two, mangled alike, so either answers).
func (rd *reader) pendingDecl(p pendingCall, ctors map[string][]int) *Decl {
	if p.declID != "" {
		if i, ok := rd.declByID[p.declID]; ok {
			return &rd.decls[i]
		}
		return nil
	}
	for _, i := range ctors[p.class+"\x00"+p.ctorType] {
		return &rd.decls[i]
	}
	return nil
}

// classOf is the record a declaration belongs to: the enclosing
// CXXRecordDecl's name, or — for an out-of-line definition, which the
// dump writes at namespace scope — the record its parentDeclContextId
// names.
func (rd *reader) classOf(parentID string) string {
	if parentID != "" {
		if n, ok := rd.records[parentID]; ok {
			return n
		}
	}
	return rd.curClass
}

// qualify is a site's Caller: a method carries its class, Class::name.
func qualify(class, name string) string {
	if class == "" {
		return name
	}
	return class + "::" + name
}

// className reduces a constructed expression's type to the record's own
// name, which is what a declaration records: the qualifiers clang prints
// (const/volatile, the struct/class/union tag, the namespace path) are
// stripped.
func className(qualType string) string {
	s := strings.TrimSpace(qualType)
	for _, prefix := range []string{"const ", "volatile ", "struct ", "class ", "union "} {
		for strings.HasPrefix(s, prefix) {
			s = strings.TrimSpace(strings.TrimPrefix(s, prefix))
		}
	}
	if i := strings.LastIndex(s, "::"); i >= 0 {
		s = s[i+2:]
	}
	return s
}

// isDeclKind is the set of nodes that declare a callable: C's
// FunctionDecl and C++'s four member shapes. A FunctionTemplateDecl is
// not one of them — the FunctionDecls inside it, the pattern and each
// specialisation, are the declarations, at the template's own line.
func isDeclKind(kind string) bool {
	switch kind {
	case "FunctionDecl", "CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl", "CXXConversionDecl":
		return true
	}
	return false
}

// declKind maps a declaration node to the kind its targets carry.
func declKind(kind string) string {
	switch kind {
	case "CXXConstructorDecl":
		return "constructor"
	case "CXXDestructorDecl":
		return "destructor"
	case "CXXMethodDecl", "CXXConversionDecl":
		return "method"
	}
	return "function"
}

// isCallKind is the set of nodes whose first child is a callee to peel.
func isCallKind(kind string) bool {
	switch kind {
	case "CallExpr", "CXXMemberCallExpr", "CXXOperatorCallExpr":
		return true
	}
	return false
}

// isUnevaluatedKind is the set of nodes whose operand the program never
// evaluates, so no call written under one is a call the program makes
// (ADR-121 §3): `sizeof` and `alignof` (one node, distinguished only by
// a "name" field the rule does not need), a `noexcept` expression, and a
// requires-expression's requirements. CXXTypeidExpr is deliberately not
// one of them — `typeid`'s operand IS evaluated when it is a glvalue of
// polymorphic class type ([expr.typeid]/3), which the node does not say,
// and keeping the site is the conservative side, lane A's rule too
// (ADR-121 §1). A `decltype` needs no rule: its operand is printed as
// part of a type string and never reaches the reader as a node.
func isUnevaluatedKind(kind string) bool {
	switch kind {
	case "UnaryExprOrTypeTraitExpr", "CXXNoexceptExpr", "RequiresExpr":
		return true
	}
	return false
}

// isConstructKind is the set of nodes that construct an object;
// CXXTemporaryObjectExpr is CXXConstructExpr's subclass in the dump.
func isConstructKind(kind string) bool {
	return kind == "CXXConstructExpr" || kind == "CXXTemporaryObjectExpr"
}

// calleeResult is a call's peeled callee: its position (rule 4) and,
// when it names a declaration — a DeclRefExpr's referencedDecl or a
// MemberExpr's referencedMemberDecl — that declaration's name and id.
type calleeResult struct {
	pos      pos
	isFunc   bool
	name     string
	declID   string
	isMember bool
	// memberPos is a MemberExpr's range end: the member's own token. The
	// node carries no "loc" and its range begins at the object, so a
	// member call written across lines keys on a line its member is not
	// on unless the site is taken from here (ADR-113 §3, H-28).
	memberPos pos
	// endPos is a DeclRefExpr's range end — the callee's own name token,
	// where its begin is the qualifier's first — kept for the one shape
	// that needs it, a qualifier spelled in a macro's body (H-31).
	endPos pos
}

// peelCallee decodes a callee expression node (its opening '{' not yet
// consumed), peeling through ImplicitCastExpr, ParenExpr and a unary
// `*`/`&` to the expression that remains, and returns its position and,
// if it names a declaration — a DeclRefExpr's referencedDecl or a C++
// MemberExpr's referencedMemberDecl — that declaration's name and id. fn
// is the enclosing function (Caller) for any call recorded along the way
// — a callee that is itself a call (`get_fn()(2)`) is two sites, so a
// call found here is peeled for ITS OWN callee and recorded as a call in
// its own right (never dropped), and this callee then resolves dynamic:
// a call through the value the inner call returns.
func (rd *reader) peelCallee(fn string) (calleeResult, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return calleeResult{}, err
	}
	var kind, opcode, name, refKind, refName, refID, memberID string
	var rangeBegin, rangeEnd pos
	var child *calleeResult

	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return calleeResult{}, err
		}
		switch key {
		case "kind":
			if kind, err = nextString(rd.dec); err != nil {
				return calleeResult{}, err
			}
		case "opcode":
			if opcode, err = nextString(rd.dec); err != nil {
				return calleeResult{}, err
			}
		case "name":
			if name, err = nextString(rd.dec); err != nil {
				return calleeResult{}, err
			}
		case "referencedMemberDecl":
			if memberID, err = nextString(rd.dec); err != nil {
				return calleeResult{}, err
			}
		case "range":
			if rangeBegin, rangeEnd, err = rd.readRange(); err != nil {
				return calleeResult{}, err
			}
		case "referencedDecl":
			if refKind, refName, refID, err = rd.readReferencedDecl(); err != nil {
				return calleeResult{}, err
			}
		case "inner":
			if err := expectDelim(rd.dec, '['); err != nil {
				return calleeResult{}, err
			}
			first := true
			for rd.dec.More() {
				switch {
				case first && isCallKind(kind):
					innerCallee, err := rd.peelCallee(fn)
					if err != nil {
						return calleeResult{}, err
					}
					rd.record(innerCallee, fn, kind)
				case first && isPeelable(kind, opcode):
					cr, err := rd.peelCallee(fn)
					if err != nil {
						return calleeResult{}, err
					}
					child = &cr
				default:
					if _, err := rd.walkNode(fn); err != nil {
						return calleeResult{}, err
					}
				}
				first = false
			}
			if err := expectDelim(rd.dec, ']'); err != nil {
				return calleeResult{}, err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return calleeResult{}, err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return calleeResult{}, err
	}
	if child != nil {
		return *child, nil
	}
	if kind == "MemberExpr" {
		return calleeResult{pos: rangeBegin, memberPos: rangeEnd, isFunc: memberID != "",
			name: name, declID: memberID, isMember: true}, nil
	}
	cr := calleeResult{pos: rangeBegin, isFunc: kind == "DeclRefExpr" && isDeclKind(refKind), name: refName, declID: refID}
	if kind == "DeclRefExpr" {
		cr.endPos = rangeEnd
	}
	return cr, nil
}

// isPeelable is ADR-110's callee-peeling set: implicit casts,
// parentheses, and a unary dereference or address-of.
func isPeelable(kind, opcode string) bool {
	switch kind {
	case "ImplicitCastExpr", "ParenExpr":
		return true
	case "UnaryOperator":
		return opcode == "*" || opcode == "&"
	}
	return false
}

// readRange decodes a "range" object (its opening '{' not yet consumed)
// and returns both its "begin" and its "end" position. Almost every
// caller wants "begin" — the callee name token, not the parenthesis,
// positions a call — but a MemberExpr, which carries no "loc", spells
// the object at its begin and the member's own token at its end
// (ADR-113 §3, H-28), and a DeclRefExpr's end is the callee's own name
// where its begin is a qualifier a macro body supplied (H-31).
func (rd *reader) readRange() (begin, end pos, err error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return pos{}, pos{}, err
	}
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return pos{}, pos{}, err
		}
		switch key {
		case "begin":
			if begin, err = rd.readPos(); err != nil {
				return pos{}, pos{}, err
			}
		case "end":
			if end, err = rd.readPos(); err != nil {
				return pos{}, pos{}, err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return pos{}, pos{}, err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return pos{}, pos{}, err
	}
	return begin, end, nil
}

// readReferencedDecl decodes a "referencedDecl" object (its opening '{'
// not yet consumed) and returns its kind, name and id. The object is a
// stub: it carries no mangled name, so the id is what names the
// declaration the dump wrote in full elsewhere.
func (rd *reader) readReferencedDecl() (kind, name, id string, err error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return "", "", "", err
	}
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return "", "", "", err
		}
		switch key {
		case "kind":
			if kind, err = nextString(rd.dec); err != nil {
				return "", "", "", err
			}
		case "name":
			if name, err = nextString(rd.dec); err != nil {
				return "", "", "", err
			}
		case "id":
			if id, err = nextString(rd.dec); err != nil {
				return "", "", "", err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return "", "", "", err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return "", "", "", err
	}
	return kind, name, id, nil
}

// readQualType decodes a "type" or "ctorType" value (its opening '{' not
// yet consumed) and returns its "qualType".
func (rd *reader) readQualType() (string, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return "", err
	}
	qual := ""
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return "", err
		}
		if key == "qualType" {
			if qual, err = nextString(rd.dec); err != nil {
				return "", err
			}
			continue
		}
		if err := rd.skipKeyValue(key); err != nil {
			return "", err
		}
	}
	return qual, expectDelim(rd.dec, '}')
}

// readPos decodes a "loc" or "range"."begin"/"end" value: either a
// plain location (first key "offset") or a macro spelling/expansion
// pair (first key "spellingLoc").
func (rd *reader) readPos() (pos, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return pos{}, err
	}
	if !rd.dec.More() {
		return pos{}, expectDelim(rd.dec, '}')
	}
	key, err := nextKey(rd.dec)
	if err != nil {
		return pos{}, err
	}
	switch key {
	case "offset":
		p, _, err := rd.locationTail()
		return pos{plain: p}, err
	case "spellingLoc":
		sp, _, err := rd.readPlainLocationValue()
		if err != nil {
			return pos{}, err
		}
		k2, err := nextKey(rd.dec)
		if err != nil {
			return pos{}, err
		}
		if k2 != "expansionLoc" {
			return pos{}, fmt.Errorf("clang: expected expansionLoc after spellingLoc, got %q", k2)
		}
		ep, argExp, err := rd.readPlainLocationValue()
		if err != nil {
			return pos{}, err
		}
		if err := expectDelim(rd.dec, '}'); err != nil {
			return pos{}, err
		}
		return pos{macro: true, spelling: sp, expansion: ep, argExpansion: argExp}, nil
	default:
		if err := rd.skipKeyValue(key); err != nil {
			return pos{}, err
		}
		for rd.dec.More() {
			k, err := nextKey(rd.dec)
			if err != nil {
				return pos{}, err
			}
			if err := rd.skipKeyValue(k); err != nil {
				return pos{}, err
			}
		}
		return pos{}, expectDelim(rd.dec, '}')
	}
}

// readPlainLocationValue decodes a key's value that must be a plain
// location object (spellingLoc / expansionLoc): its opening '{' and
// first key ("offset") are consumed here, then locationTail reads the
// rest.
func (rd *reader) readPlainLocationValue() (rawPos, bool, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return rawPos{}, false, err
	}
	key, err := nextKey(rd.dec)
	if err != nil {
		return rawPos{}, false, err
	}
	if key != "offset" {
		return rawPos{}, false, fmt.Errorf("clang: expected offset key, got %q", key)
	}
	return rd.locationTail()
}

// locationTail decodes a location object's remaining fields, the
// "offset" key already having been read (its value not yet consumed).
// It carries the reader's file/line state forward through an omitted
// "file" or "line", records an in-repo path into files, and notices the
// unit's own main file (a location with no "includedFrom").
func (rd *reader) locationTail() (rawPos, bool, error) {
	if err := rd.skipAny(); err != nil { // offset's value
		return rawPos{}, false, err
	}
	path, inRepo, pseudo, line := rd.curPath, rd.curInRepo, rd.curPseudo, rd.curLine
	col := 0
	hasIncludedFrom := false
	argExp := false
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return rawPos{}, false, err
		}
		switch key {
		case "file":
			raw, err := nextString(rd.dec)
			if err != nil {
				return rawPos{}, false, err
			}
			if isPseudoFile(raw) {
				path, inRepo, pseudo = raw, false, true
			} else {
				path, inRepo = normalize(raw, rd.dir, rd.repo)
				pseudo = false
			}
		case "line":
			n, err := nextInt(rd.dec)
			if err != nil {
				return rawPos{}, false, err
			}
			line = n
		case "col":
			n, err := nextInt(rd.dec)
			if err != nil {
				return rawPos{}, false, err
			}
			col = n
		case "isMacroArgExpansion":
			if argExp, err = nextBool(rd.dec); err != nil {
				return rawPos{}, false, err
			}
		case "includedFrom":
			hasIncludedFrom = true
			if err := rd.skipValueAsObject(); err != nil {
				return rawPos{}, false, err
			}
		default: // tokLen, and anything future
			if err := rd.skipAny(); err != nil {
				return rawPos{}, false, err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return rawPos{}, false, err
	}
	rd.curPath, rd.curInRepo, rd.curPseudo, rd.curLine = path, inRepo, pseudo, line
	if inRepo {
		rd.files[path] = true
	}
	if !hasIncludedFrom && path != "" && !pseudo && rd.mainFile == "" {
		rd.mainFile = path
	}
	return rawPos{Path: path, InRepo: inRepo, Pseudo: pseudo, Line: line, Col: col}, argExp, nil
}

// skipKeyValue discards one key's value generically, except
// "includedFrom", whose object must be walked (not treated as a
// location) so it never moves the carried file/line state.
func (rd *reader) skipKeyValue(key string) error {
	if key == "includedFrom" {
		return rd.skipValueAsObject()
	}
	return rd.skipAny()
}

// skipValueAsObject discards the next value, which is expected to be an
// object, via objectBody.
func (rd *reader) skipValueAsObject() error {
	tok, err := rd.dec.Token()
	if err != nil {
		return err
	}
	if d, ok := tok.(json.Delim); ok && d == '{' {
		return rd.objectBody()
	}
	return nil
}

// objectBody discards an object's fields (its opening '{' already
// consumed), still resolving a nested location it finds (so the carried
// file/line state and the files set stay correct) — an object whose
// first key is "offset" is a location; every other object, including
// "includedFrom", is not.
func (rd *reader) objectBody() error {
	if !rd.dec.More() {
		return expectDelim(rd.dec, '}')
	}
	key, err := nextKey(rd.dec)
	if err != nil {
		return err
	}
	if key == "offset" {
		_, _, err := rd.locationTail()
		return err
	}
	if err := rd.skipKeyValue(key); err != nil {
		return err
	}
	for rd.dec.More() {
		k, err := nextKey(rd.dec)
		if err != nil {
			return err
		}
		if err := rd.skipKeyValue(k); err != nil {
			return err
		}
	}
	return expectDelim(rd.dec, '}')
}

// skipAny discards the next JSON value of any shape.
func (rd *reader) skipAny() error {
	tok, err := rd.dec.Token()
	if err != nil {
		return err
	}
	d, ok := tok.(json.Delim)
	if !ok {
		return nil
	}
	switch d {
	case '{':
		return rd.objectBody()
	case '[':
		for rd.dec.More() {
			if err := rd.skipAny(); err != nil {
				return err
			}
		}
		return expectDelim(rd.dec, ']')
	}
	return nil
}

// expectDelim consumes the next token and requires it to be d.
func expectDelim(dec *json.Decoder, d json.Delim) error {
	tok, err := dec.Token()
	if err != nil {
		return err
	}
	if got, ok := tok.(json.Delim); !ok || got != d {
		return fmt.Errorf("clang: expected %q, got %v", d, tok)
	}
	return nil
}

// nextKey reads the next token and requires it to be an object key.
func nextKey(dec *json.Decoder) (string, error) {
	tok, err := dec.Token()
	if err != nil {
		return "", err
	}
	s, ok := tok.(string)
	if !ok {
		return "", fmt.Errorf("clang: expected object key, got %v", tok)
	}
	return s, nil
}

// nextString reads the next token and requires it to be a string.
func nextString(dec *json.Decoder) (string, error) {
	tok, err := dec.Token()
	if err != nil {
		return "", err
	}
	s, ok := tok.(string)
	if !ok {
		return "", fmt.Errorf("clang: expected string, got %v", tok)
	}
	return s, nil
}

// nextBool reads the next token and requires it to be a bool.
func nextBool(dec *json.Decoder) (bool, error) {
	tok, err := dec.Token()
	if err != nil {
		return false, err
	}
	b, ok := tok.(bool)
	if !ok {
		return false, fmt.Errorf("clang: expected bool, got %v", tok)
	}
	return b, nil
}

// nextInt reads the next token and requires it to be a JSON number.
func nextInt(dec *json.Decoder) (int, error) {
	tok, err := dec.Token()
	if err != nil {
		return 0, err
	}
	n, ok := tok.(float64)
	if !ok {
		return 0, fmt.Errorf("clang: expected number, got %v", tok)
	}
	return int(n), nil
}
