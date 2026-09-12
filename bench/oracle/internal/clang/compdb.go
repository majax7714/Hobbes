package clang

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// CompdbEntry is one compile database entry (the JSON Compilation
// Database format clang tools share): a translation unit's working
// directory and its command, spelled either as a pre-split Arguments
// list or a shell-quoted Command string.
type CompdbEntry struct {
	Directory string   `json:"directory"`
	File      string   `json:"file,omitempty"`
	Arguments []string `json:"arguments,omitempty"`
	Command   string   `json:"command,omitempty"`
}

// Argv is the entry's argv: Arguments when the entry carries one,
// otherwise Command split shell-style (quotes and backslashes).
func (e CompdbEntry) Argv() []string {
	if len(e.Arguments) > 0 {
		return e.Arguments
	}
	return shellSplit(e.Command)
}

// LoadCompdb reads a compile database file (a JSON array of entries).
func LoadCompdb(path string) ([]CompdbEntry, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var entries []CompdbEntry
	if err := json.Unmarshal(raw, &entries); err != nil {
		return nil, err
	}
	return entries, nil
}

// dbCandidates are the repo-carried compile database locations, in the
// order ADR-109 checks them.
var dbCandidates = []string{"compile_commands.json", filepath.Join("build", "compile_commands.json")}

// makefileNames are the Makefile spellings GNU make reads, in its own
// order (mirrors the ingest's C_MAKEFILES).
var makefileNames = []string{"GNUmakefile", "makefile", "Makefile"}

// DatabaseSource decides where one C build root's compile database
// comes from, in ADR-109's order (Max's order, mirrored from the
// ingest's c_compdb_source so the oracle grades what the product
// indexed): a compile_commands.json the repo carries at the root or in
// build/, usable when every entry's directory is relative or lies
// under repo; else a CMakeLists.txt at the root; else a Makefile at the
// root; else none. rel is the carried database's path (relative to
// root) when source is "repo"; "" otherwise. Reads files, runs nothing.
func DatabaseSource(repo, module string) (source, rel string) {
	root := filepath.Join(repo, module)
	for _, cand := range dbCandidates {
		p := filepath.Join(root, cand)
		if _, err := os.Stat(p); err != nil {
			continue
		}
		if carriedCompdbUsable(repo, p) {
			return "repo", cand
		}
	}
	if _, err := os.Stat(filepath.Join(root, "CMakeLists.txt")); err == nil {
		return "cmake", ""
	}
	for _, name := range makefileNames {
		if _, err := os.Stat(filepath.Join(root, name)); err == nil {
			return "make", ""
		}
	}
	return "", ""
}

// carriedCompdbUsable reports whether a repo-carried compile database
// parses, holds at least one entry, and names only directories that are
// relative or lie under repo (an entry from another machine's absolute
// build tree does not rebase here).
func carriedCompdbUsable(repo, path string) bool {
	entries, err := LoadCompdb(path)
	if err != nil || len(entries) == 0 {
		return false
	}
	for _, e := range entries {
		if e.Directory == "" {
			return false
		}
		if filepath.IsAbs(e.Directory) {
			rel, err := filepath.Rel(repo, e.Directory)
			if err != nil || rel == ".." || strings.HasPrefix(rel, "../") {
				return false
			}
		}
	}
	return true
}

// oneArgFlags take their value as a separate following argument
// (never attached, unlike -o); FilterArgs drops the flag and its value.
var oneArgFlags = map[string]bool{"-o": true, "-MF": true, "-MT": true, "-MQ": true}

// bareFlags take no value; FilterArgs drops them alone.
var bareFlags = map[string]bool{"-c": true, "-MD": true, "-MMD": true, "-MP": true}

// FilterArgs drops argv[0] (the compiler the entry names), the output
// and dependency flags (-c, -o/-oX, -MD, -MMD, -MP, -MF/-MT/-MQ with
// their values), and keeps the rest — the entry's own defines, include
// paths and the source file — for a `clang -fsyntax-only -Xclang
// -ast-dump=json` run.
func FilterArgs(argv []string) []string {
	if len(argv) == 0 {
		return nil
	}
	var out []string
	skip := false
	for _, a := range argv[1:] {
		if skip {
			skip = false
			continue
		}
		switch {
		case bareFlags[a]:
			continue
		case oneArgFlags[a]:
			skip = true
			continue
		case strings.HasPrefix(a, "-o") && len(a) > len("-o"):
			continue
		default:
			out = append(out, a)
		}
	}
	return out
}

// shellSplit tokenizes a compile database's "command" string the way a
// POSIX shell would: whitespace-separated, honoring single quotes
// (literal), double quotes (backslash escapes \, $, ", ` inside), and a
// backslash escaping the next character outside quotes.
func shellSplit(s string) []string {
	var out []string
	var cur strings.Builder
	open := false
	inSingle, inDouble := false, false
	runes := []rune(s)
	for i := 0; i < len(runes); i++ {
		c := runes[i]
		switch {
		case inSingle:
			if c == '\'' {
				inSingle = false
			} else {
				cur.WriteRune(c)
			}
		case inDouble:
			switch {
			case c == '"':
				inDouble = false
			case c == '\\' && i+1 < len(runes) && strings.ContainsRune("\\\"$`", runes[i+1]):
				i++
				cur.WriteRune(runes[i])
			default:
				cur.WriteRune(c)
			}
		case c == '\'':
			inSingle, open = true, true
		case c == '"':
			inDouble, open = true, true
		case c == '\\' && i+1 < len(runes):
			i++
			cur.WriteRune(runes[i])
			open = true
		case c == ' ' || c == '\t' || c == '\n':
			if open || cur.Len() > 0 {
				out = append(out, cur.String())
				cur.Reset()
				open = false
			}
		default:
			cur.WriteRune(c)
			open = true
		}
	}
	if open || cur.Len() > 0 {
		out = append(out, cur.String())
	}
	return out
}
