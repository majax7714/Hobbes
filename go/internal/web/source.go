package web

import (
	"bytes"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strconv"
	"strings"
)

const (
	// maxSourceBytes caps a provenance read. Pins cite source lines; a
	// file larger than this is not what a claim points at.
	maxSourceBytes = 2 << 20
	// maxPatchBytes caps a diff. The Diff tab is the last resort in the
	// §7 review order, not a place to stream a megabyte of patch.
	maxPatchBytes = 1 << 20
)

// errTFState is the refusal ADR-011's floor implies at the read surface:
// state files carry secrets and no Hobbes component serves them.
var errTFState = errors.New("terraform state is never read by Hobbes (ADR-011)")

// isTFState matches .tfstate and its backups/variants, the same shapes
// the box policy denies.
func isTFState(rel string) bool {
	base := strings.ToLower(path.Base(rel))
	return strings.HasSuffix(base, ".tfstate") || strings.Contains(base, ".tfstate.")
}

// resolveRepoFile turns a request path into an absolute path inside the
// repo, or an error. Traversal, absolute paths, symlinks pointing out of
// the repo, and tfstate are all refused.
func (s *Server) resolveRepoFile(rel string) (string, error) {
	if rel == "" {
		return "", errors.New("path is required")
	}
	rel = filepath.ToSlash(rel)
	if strings.HasPrefix(rel, "/") || filepath.IsAbs(rel) || strings.Contains(rel, "\\") {
		return "", errors.New("path must be repo-relative")
	}
	if path.Clean(rel) != rel {
		return "", errors.New("path must be normalized")
	}
	for _, seg := range strings.Split(rel, "/") {
		if seg == ".." {
			return "", errors.New("path must not traverse out of the repo")
		}
	}
	if isTFState(rel) {
		return "", errTFState
	}
	full := filepath.Join(s.cfg.RepoRoot, filepath.FromSlash(rel))
	// EvalSymlinks after joining: a symlinked path inside the repo that
	// resolves outside it is still an escape.
	real, err := filepath.EvalSymlinks(full)
	if err != nil {
		return "", err
	}
	root, err := filepath.EvalSymlinks(s.cfg.RepoRoot)
	if err != nil {
		return "", err
	}
	if real != root && !strings.HasPrefix(real, root+string(filepath.Separator)) {
		return "", errors.New("path resolves outside the repo")
	}
	return real, nil
}

// sourceFile is the provenance view: a pinned file's lines, plus enough
// context for the app to highlight and link.
type sourceFile struct {
	Path      string   `json:"path"`
	Lines     []string `json:"lines"`
	Truncated bool     `json:"truncated"`
	Bytes     int      `json:"bytes"`
}

func (s *Server) handleSource(w http.ResponseWriter, r *http.Request) {
	rel := r.URL.Query().Get("path")
	full, err := s.resolveRepoFile(rel)
	if err != nil {
		status := http.StatusBadRequest
		if os.IsNotExist(err) {
			status = http.StatusNotFound
		}
		if errors.Is(err, errTFState) {
			status = http.StatusForbidden
		}
		writeError(w, status, err.Error(), "")
		return
	}
	info, err := os.Stat(full)
	if err != nil {
		writeError(w, http.StatusNotFound, err.Error(), "")
		return
	}
	if info.IsDir() {
		writeError(w, http.StatusBadRequest, "path is a directory", "")
		return
	}
	data, err := os.ReadFile(full)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	out := sourceFile{Path: rel, Bytes: len(data)}
	if len(data) > maxSourceBytes {
		data, out.Truncated = data[:maxSourceBytes], true
	}
	// A NUL in the head is the usual binary tell; rendering one as text
	// helps nobody and can be megabytes of noise.
	head := data
	if len(head) > 8192 {
		head = head[:8192]
	}
	if bytes.IndexByte(head, 0) >= 0 {
		writeError(w, http.StatusUnsupportedMediaType, "file is binary", "")
		return
	}
	text := strings.TrimSuffix(string(data), "\n")
	if text == "" {
		out.Lines = []string{}
	} else {
		out.Lines = strings.Split(text, "\n")
	}
	writeJSON(w, http.StatusOK, out)
}

// --- diff -------------------------------------------------------------------

// diffFile is one file's line churn in a diff.
type diffFile struct {
	Path    string `json:"path"`
	Added   int    `json:"added"`
	Removed int    `json:"removed"`
	Binary  bool   `json:"binary"`
}

// diffResult is the Diff tab's payload: what was compared, the per-file
// churn, and the patch itself.
type diffResult struct {
	Mode      string     `json:"mode"` // working-tree | range
	Base      string     `json:"base"`
	Head      string     `json:"head"`
	Files     []diffFile `json:"files"`
	Patch     string     `json:"patch"`
	Truncated bool       `json:"truncated"`
}

// validRef rejects anything that could be read as a git option, then
// asks git whether it resolves.
func (s *Server) validRef(ref string) error {
	if ref == "" || strings.HasPrefix(ref, "-") {
		return fmt.Errorf("%q is not a ref", ref)
	}
	cmd := exec.Command("git", "-C", s.cfg.RepoRoot, "rev-parse", "--verify", "--quiet", ref+"^{commit}")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("unknown ref %q", ref)
	}
	return nil
}

func (s *Server) handleDiff(w http.ResponseWriter, r *http.Request) {
	base := strings.TrimSpace(r.URL.Query().Get("base"))
	head := strings.TrimSpace(r.URL.Query().Get("head"))

	out := diffResult{Files: []diffFile{}}
	var spec []string
	switch {
	case base == "" && head == "":
		// Uncommitted work is the default view: it is what the user is
		// looking at when they open the tab.
		out.Mode, out.Base, out.Head = "working-tree", "HEAD", "(working tree)"
		spec = []string{"HEAD"}
	case head == "":
		if err := s.validRef(base); err != nil {
			writeError(w, http.StatusBadRequest, err.Error(), "")
			return
		}
		out.Mode, out.Base, out.Head = "working-tree", base, "(working tree)"
		spec = []string{base}
	default:
		for _, ref := range []string{base, head} {
			if err := s.validRef(ref); err != nil {
				writeError(w, http.StatusBadRequest, err.Error(), "")
				return
			}
		}
		// Three-dot: changes head introduced since it diverged from base,
		// which is the review question, not "how do these two trees differ".
		out.Mode, out.Base, out.Head = "range", base, head
		spec = []string{base + "..." + head}
	}

	numstat, err := s.gitDiff(spec, "--numstat")
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	for _, line := range strings.Split(strings.TrimSpace(numstat), "\n") {
		if line == "" {
			continue
		}
		cols := strings.SplitN(line, "\t", 3)
		if len(cols) != 3 {
			continue
		}
		f := diffFile{Path: cols[2]}
		if cols[0] == "-" {
			f.Binary = true
		} else {
			f.Added, _ = strconv.Atoi(cols[0])
			f.Removed, _ = strconv.Atoi(cols[1])
		}
		out.Files = append(out.Files, f)
	}

	patch, err := s.gitDiff(spec)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error(), "")
		return
	}
	if len(patch) > maxPatchBytes {
		patch, out.Truncated = patch[:maxPatchBytes], true
	}
	out.Patch = patch
	writeJSON(w, http.StatusOK, out)
}

// gitDiff runs `git diff [flags] <spec...> --`. The trailing `--` and the
// validated, non-flag-shaped refs keep a query parameter from turning
// into a git option.
func (s *Server) gitDiff(spec []string, flags ...string) (string, error) {
	args := append([]string{"-C", s.cfg.RepoRoot, "diff", "--no-color"}, flags...)
	args = append(args, spec...)
	args = append(args, "--")
	cmd := exec.Command("git", args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	stdout, err := cmd.Output()
	if err != nil {
		msg := strings.TrimSpace(stderr.String())
		if msg == "" {
			msg = err.Error()
		}
		return "", errors.New("git diff failed: " + msg)
	}
	return string(stdout), nil
}

// refInfo is one entry in the ref picker.
type refInfo struct {
	Name    string `json:"name"`
	Kind    string `json:"kind"` // branch | tag | commit
	Subject string `json:"subject,omitempty"`
}

func (s *Server) handleRefs(w http.ResponseWriter, r *http.Request) {
	refs := []refInfo{}
	branches := s.gitOutput("for-each-ref", "--sort=-committerdate", "--count=30",
		"--format=%(refname:short)\t%(contents:subject)", "refs/heads")
	tags := s.gitOutput("for-each-ref", "--sort=-creatordate", "--count=20",
		"--format=%(refname:short)\t%(contents:subject)", "refs/tags")
	commits := s.gitOutput("log", "-n", "30", "--format=%h\t%s")

	for _, group := range []struct{ out, kind string }{
		{branches, "branch"}, {tags, "tag"}, {commits, "commit"},
	} {
		for _, line := range strings.Split(strings.TrimSpace(group.out), "\n") {
			if line == "" {
				continue
			}
			name, subject, _ := strings.Cut(line, "\t")
			refs = append(refs, refInfo{Name: name, Kind: group.kind, Subject: subject})
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"refs": refs, "head": s.gitOutput("rev-parse", "--abbrev-ref", "HEAD")})
}
