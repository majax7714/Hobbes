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

	mainFile string
	files    map[string]bool
	decls    []Decl
	calls    []Call
}

// ReadDump reads one translation unit's clang AST dump (`clang
// -fsyntax-only -Xclang -ast-dump=json`): a stream of JSON tokens read
// in document order, never a whole-document unmarshal — a real dump is
// 25-35 MB, almost all system headers. dir is the compile entry's own
// directory; repo is the repository root, both absolute. An
// unparseable dump returns an error, never a partial shard.
func ReadDump(r io.Reader, dir, repo string) (*Shard, error) {
	rd := &reader{dec: json.NewDecoder(r), dir: dir, repo: repo, files: map[string]bool{}}
	if _, err := rd.walkNode(""); err != nil {
		return nil, fmt.Errorf("clang: %w", err)
	}
	s := &Shard{File: rd.mainFile, Decls: rd.decls, Calls: rd.calls}
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
// consumed), recording function declarations and in-repo call sites as
// it goes, and returns the node's own "kind" so a FunctionDecl's own
// walk can notice a direct CompoundStmt child (a definition). fn is the
// name of the nearest enclosing FunctionDecl (Caller); "" at the top.
func (rd *reader) walkNode(fn string) (string, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return "", err
	}
	var kind, name, storageClass string
	var isImplicit bool
	var nodeLoc pos
	hasCompound := false
	var call *Call

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
		case "name":
			if name, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "storageClass":
			if storageClass, err = nextString(rd.dec); err != nil {
				return "", err
			}
		case "isImplicit":
			if isImplicit, err = nextBool(rd.dec); err != nil {
				return "", err
			}
		case "loc":
			if nodeLoc, err = rd.readPos(); err != nil {
				return "", err
			}
		case "inner":
			if kind == "CallExpr" {
				if call, err = rd.walkCallExprInner(fn); err != nil {
					return "", err
				}
			} else {
				childFn := fn
				if kind == "FunctionDecl" {
					childFn = name
				}
				if hasCompound, err = rd.walkChildren(kind, childFn); err != nil {
					return "", err
				}
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

	switch kind {
	case "FunctionDecl":
		p, _ := nodeLoc.resolve()
		rd.decls = append(rd.decls, Decl{
			Name: name, Body: hasCompound, Static: storageClass == "static",
			Implicit: isImplicit, InRepo: p.InRepo,
			Pos: edges.Pos{Path: p.Path, Line: p.Line},
		})
	case "CallExpr":
		if call != nil {
			rd.calls = append(rd.calls, *call)
		}
	}
	return kind, nil
}

// walkChildren decodes an "inner" array of ordinary AST node children
// (every kind but CallExpr, whose callee needs peeling —
// walkCallExprInner handles that). It reports whether any direct child
// is a CompoundStmt, so its FunctionDecl caller can tell a definition
// from a bare declaration.
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
		if parentKind == "FunctionDecl" && kind == "CompoundStmt" {
			hasCompound = true
		}
	}
	if err := expectDelim(rd.dec, ']'); err != nil {
		return false, err
	}
	return hasCompound, nil
}

// walkCallExprInner decodes a CallExpr's "inner" array: its first
// element is the callee, peeled to a mode and position; the rest are
// ordinary children (a call's arguments can hold further calls).
func (rd *reader) walkCallExprInner(fn string) (*Call, error) {
	if err := expectDelim(rd.dec, '['); err != nil {
		return nil, err
	}
	var call *Call
	first := true
	for rd.dec.More() {
		if first {
			cr, err := rd.peelCallee(fn)
			if err != nil {
				return nil, err
			}
			call = rd.buildCall(cr, fn)
		} else if _, err := rd.walkNode(fn); err != nil {
			return nil, err
		}
		first = false
	}
	if err := expectDelim(rd.dec, ']'); err != nil {
		return nil, err
	}
	return call, nil
}

// buildCall turns a peeled callee into a Call, or nil when its site
// does not lie in the repo (rule: only in-repo call sites are sites at
// all).
func (rd *reader) buildCall(cr calleeResult, fn string) *Call {
	sitePos, macroBody := cr.pos.resolve()
	if !sitePos.InRepo {
		return nil
	}
	spell := cr.pos.spellingPos()
	mode, callee := "dynamic", ""
	if cr.isFunc {
		callee = cr.name
		mode = "static"
		if macroBody {
			mode = "macro"
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

// calleeResult is a CallExpr's peeled callee: its position (rule 4) and,
// when it is a DeclRefExpr naming a FunctionDecl, the direct call it
// names.
type calleeResult struct {
	pos    pos
	isFunc bool
	name   string
}

// peelCallee decodes a callee expression node (its opening '{' not yet
// consumed), peeling through ImplicitCastExpr, ParenExpr and a unary
// `*`/`&` to the expression that remains, and returns its position and,
// if it is a DeclRefExpr naming a FunctionDecl, that name. fn is the
// enclosing function (Caller) for any call recorded along the way — a
// callee that is itself a call (`get_fn()(2)`) is two sites, so a
// CallExpr found here is peeled for ITS OWN callee and recorded as a
// call in its own right (never dropped), and this callee then resolves
// dynamic: a call through the value the inner call returns.
func (rd *reader) peelCallee(fn string) (calleeResult, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return calleeResult{}, err
	}
	var kind, opcode, refKind, refName string
	var rangeBegin pos
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
		case "range":
			if rangeBegin, err = rd.readRangeBegin(); err != nil {
				return calleeResult{}, err
			}
		case "referencedDecl":
			if refKind, refName, err = rd.readReferencedDecl(); err != nil {
				return calleeResult{}, err
			}
		case "inner":
			if err := expectDelim(rd.dec, '['); err != nil {
				return calleeResult{}, err
			}
			first := true
			for rd.dec.More() {
				switch {
				case first && kind == "CallExpr":
					innerCallee, err := rd.peelCallee(fn)
					if err != nil {
						return calleeResult{}, err
					}
					if c := rd.buildCall(innerCallee, fn); c != nil {
						rd.calls = append(rd.calls, *c)
					}
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
	return calleeResult{pos: rangeBegin, isFunc: kind == "DeclRefExpr" && refKind == "FunctionDecl", name: refName}, nil
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

// readRangeBegin decodes a "range" object (its opening '{' not yet
// consumed) and returns its "begin" position; "end" is consumed for the
// carried location state but otherwise unused (rule: the callee name
// token, not the parenthesis, positions a call).
func (rd *reader) readRangeBegin() (pos, error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return pos{}, err
	}
	var begin pos
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return pos{}, err
		}
		switch key {
		case "begin":
			if begin, err = rd.readPos(); err != nil {
				return pos{}, err
			}
		case "end":
			if _, err = rd.readPos(); err != nil {
				return pos{}, err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return pos{}, err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return pos{}, err
	}
	return begin, nil
}

// readReferencedDecl decodes a "referencedDecl" object (its opening '{'
// not yet consumed) and returns its kind and name.
func (rd *reader) readReferencedDecl() (kind, name string, err error) {
	if err := expectDelim(rd.dec, '{'); err != nil {
		return "", "", err
	}
	for rd.dec.More() {
		key, err := nextKey(rd.dec)
		if err != nil {
			return "", "", err
		}
		switch key {
		case "kind":
			if kind, err = nextString(rd.dec); err != nil {
				return "", "", err
			}
		case "name":
			if name, err = nextString(rd.dec); err != nil {
				return "", "", err
			}
		default:
			if err := rd.skipAny(); err != nil {
				return "", "", err
			}
		}
	}
	if err := expectDelim(rd.dec, '}'); err != nil {
		return "", "", err
	}
	return kind, name, nil
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
