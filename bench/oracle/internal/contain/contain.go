// Package contain runs the executing oracles inside the sandbox image
// (ADR-092 phase 2). O6 (the Python trace) runs the target's test suite;
// O7 (the MIR walker) compiles the target, which runs its build scripts
// and proc macros. Both execute repo-authored code, so both fall under
// the rule the ingest lane already follows — sandbox whatever executes
// repo-authored code — and the guarantee it carries: repo code never
// executes on the host.
//
// The mount shape is the verifier role's, verbatim (ADR-060): the repo
// tree as a podman overlay (":O") at its host path — a writable view
// whose every write lands in a throwaway layer, because a plain ro mount
// breaks pytest's caches and cargo's build dirs before the work starts
// (C-43) — plus the cell's output directory rw, the Hobbes cache rw (the
// cargo registry lives there, as it does for the ingest), and whatever
// tool trees the step needs ro at their host paths: the pinned nightly
// sysroot and the driver for O7, the interpreter chain for O6. Network:
// none for the step that runs the repo; a separate fetch container
// (`cargo fetch`, no repo code) reaches the registry first.
//
// This is the oracle lane's own copy of the planner the pipeline has in
// `extract/containment.py` — bench tooling, its own module (D1), the
// same rules: mounts derived, every one at its host path, a static
// profile per step, no policy chain. Without podman or the image an
// executing step refuses (never falls back to the host); the named
// escape hatch HOBBES_UNCONTAINED=1 runs it on the host and the export
// records that it did.
package contain

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

const (
	// DefaultImage is the one image (§7); HOBBES_SANDBOX_IMAGE overrides.
	DefaultImage = "hobbes-session:local"
	imageEnv     = "HOBBES_SANDBOX_IMAGE"
	// UncontainedEnv is the named escape hatch — disclosed, never default.
	UncontainedEnv = "HOBBES_UNCONTAINED"
	cacheEnv       = "HOBBES_CACHE_DIR"
	// Path is the image-neutral PATH (mirrors the ingest planner's).
	Path = "/usr/local/java/bin:/opt/maven/bin:/usr/local/cargo/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"
)

// systemPrefixes are the image's own; a tool tree under one is never
// mounted over it.
var systemPrefixes = []string{"/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/proc", "/sys", "/dev", "/run"}

// Refusal is an executing step declining to run on a box without
// containment. A distinct type (P10, ADR-036): callers match it with
// errors.As and never turn it into a host run.
type Refusal struct{ Step, Reason string }

func (r *Refusal) Error() string {
	return fmt.Sprintf("%s refused: repo code never executes on the host (ADR-092) and %s. Build the sandbox image, or set %s=1 to run it here — disclosed, never default", r.Step, r.Reason, UncontainedEnv)
}

// Profile is a static per-step containment profile.
type Profile struct {
	Step     string
	Executes bool   // runs repo-authored code: refuse rather than run on the host
	Network  string // "none", or "" for podman's default (fetch steps only)
}

// Profiles, stated once. O6 and O7 execute; the cargo fetch does not.
// O8 (the Java javac oracle, ADR-096) executes the repo's build and,
// like the ingest lane's index-java, keeps a network: the build is the
// dependency resolution (C-66). java-build compiles the plugin itself —
// Hobbes's code, no network.
var Profiles = map[string]Profile{
	"py-trace":   {Step: "py-trace", Executes: true, Network: "none"},
	"rust-mir":   {Step: "rust-mir", Executes: true, Network: "none"},
	"fetch-rust": {Step: "fetch-rust", Executes: false, Network: ""},
	"java-javac": {Step: "java-javac", Executes: true, Network: ""},
	"java-build": {Step: "java-build", Executes: false, Network: "none"},
}

// Plan is one ready-to-run oracle container. Pure data.
type Plan struct {
	Profile Profile
	Command []string
	Dir     string   // workdir, a host path visible inside
	Tree    string   // the repo root, mounted as an overlay at its host path
	RW      []string // directories mounted rw at their host paths
	RO      []string // directories mounted ro at their host paths
	Env     []string // KEY=VALUE, on top of HOME and PATH
	Image   string
	Cache   string
}

// CacheRoot is the Hobbes cache — the one directory the ingest lane
// writes to, shared here for the cargo registry.
func CacheRoot() string {
	if v := os.Getenv(cacheEnv); v != "" {
		return v
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".hobbes", "cache")
}

// Image is the sandbox image name.
func Image() string {
	if v := os.Getenv(imageEnv); v != "" {
		return v
	}
	return DefaultImage
}

// Uncontained reports the escape hatch.
func Uncontained() bool {
	v := os.Getenv(UncontainedEnv)
	return v != "" && v != "0" && v != "false" && v != "no"
}

var (
	availOnce   sync.Once
	availReason string
)

// UnavailableReason is why containment cannot run here, or "" when it
// can. Cached: the answer does not change mid-cell.
func UnavailableReason() string {
	availOnce.Do(func() {
		if _, err := exec.LookPath("podman"); err != nil {
			availReason = "podman is not installed"
			return
		}
		if err := exec.Command("podman", "image", "exists", Image()).Run(); err != nil {
			availReason = fmt.Sprintf("image %s is not built (sandbox/README.md: `podman build`)", Image())
		}
	})
	return availReason
}

// New builds a plan: the profile looked up, the tree overlaid, the
// cache rw, RO reduced to the mounts it needs.
func New(step string, command []string, dir, tree string, rw, ro []string, env []string) (Plan, error) {
	prof, ok := Profiles[step]
	if !ok {
		return Plan{}, fmt.Errorf("contain: no profile for step %q", step)
	}
	cache := CacheRoot()
	return Plan{
		Profile: prof,
		Command: command,
		Dir:     dir,
		Tree:    tree,
		RW:      dedupe(append([]string{cache}, rw...), ""),
		RO:      MountRoots(ro, tree, cache),
		Env:     env,
		Image:   Image(),
		Cache:   cache,
	}, nil
}

// MountRoots reduces tool-tree paths to the ro mounts they need: existing,
// outside the tree (already overlaid) and the cache (already rw), outside
// the image's own prefixes, and with a path under another dropped —
// podman refuses a mount inside a mount. Unresolved: a hop may pass
// through a directory that is itself a symlink, and the container must
// see the path the link names (podman binds the real directory there).
func MountRoots(paths []string, tree, cache string) []string {
	var keep []string
	seen := map[string]bool{}
	sorted := append([]string{}, paths...)
	sort.Strings(sorted)
	for _, p := range sorted {
		if p == "" || seen[p] {
			continue
		}
		seen[p] = true
		p = filepath.Clean(p)
		if _, err := os.Stat(p); err != nil {
			continue
		}
		if (tree != "" && under(p, tree)) || under(p, cache) {
			continue
		}
		if underAny(p, systemPrefixes) || underAny(p, keep) {
			continue
		}
		keep = append(keep, p)
	}
	return keep
}

// InterpreterMounts is the chain of installs a venv's python links
// through, hop by hop, each taken two levels up so lib/ rides along; a
// hop under a system prefix is the image's to supply.
func InterpreterMounts(python string) []string {
	var out []string
	cur := python
	for i := 0; i < 16; i++ {
		fi, err := os.Lstat(cur)
		if err != nil || fi.Mode()&os.ModeSymlink == 0 {
			break
		}
		target, err := os.Readlink(cur)
		if err != nil {
			break
		}
		if !filepath.IsAbs(target) {
			target = filepath.Join(filepath.Dir(cur), target)
		}
		cur = filepath.Clean(target)
		prefix := filepath.Dir(filepath.Dir(cur))
		if !underAny(prefix, systemPrefixes) && !contains(out, prefix) {
			out = append(out, prefix)
		}
	}
	return out
}

// Mounts are the -v specs in a stable order: the tree overlay, then rw,
// then ro. No SELinux relabel: the ro trees are the user's own, and the
// overlay cannot take one (ADR-060).
func (p Plan) Mounts() []string {
	var m []string
	if p.Tree != "" {
		m = append(m, p.Tree+":"+p.Tree+":O")
	}
	for _, d := range p.RW {
		m = append(m, d+":"+d+":rw")
	}
	for _, d := range p.RO {
		m = append(m, d+":"+d+":ro")
	}
	return m
}

// PodmanArgs is the argv after `podman`.
func (p Plan) PodmanArgs() []string {
	args := []string{"run", "--rm", "--pull=never", "--security-opt", "label=disable"}
	if p.Profile.Network != "" {
		args = append(args, "--network", p.Profile.Network)
	}
	args = append(args,
		"--env", "HOME="+filepath.Join(p.Cache, "home"),
		"--env", "PATH="+Path,
		"--env", "CARGO_HOME="+filepath.Join(p.Cache, "cargo"),
		"--env", "PYTHONDONTWRITEBYTECODE=1",
	)
	for _, kv := range p.Env {
		args = append(args, "--env", kv)
	}
	args = append(args, "--workdir", p.Dir)
	for _, m := range p.Mounts() {
		args = append(args, "-v", m)
	}
	args = append(args, p.Image)
	return append(args, p.Command...)
}

// Outcome says where a step ran.
type Outcome struct {
	Contained bool
	Reason    string // set when it ran on the host
}

// Containment is the string the export records: "contained", or
// "host: <reason>".
func (o Outcome) Containment() string {
	if o.Contained {
		return "contained"
	}
	return "host: " + o.Reason
}

// Run executes the plan with stdout/stderr passed through: contained
// when the box can, on the host only when the step executes nothing or
// the escape hatch is set, refused otherwise.
func Run(p Plan) (Outcome, error) {
	reason := UnavailableReason()
	if Uncontained() {
		reason = UncontainedEnv + " is set"
	}
	if reason == "" {
		os.MkdirAll(filepath.Join(p.Cache, "home"), 0o755)
		for _, d := range p.RW {
			os.MkdirAll(d, 0o755)
		}
		cmd := exec.Command("podman", p.PodmanArgs()...)
		cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
		if err := cmd.Run(); err != nil {
			return Outcome{Contained: true}, fmt.Errorf("contain: %s: %w", p.Profile.Step, err)
		}
		return Outcome{Contained: true}, nil
	}
	if p.Profile.Executes && !Uncontained() {
		return Outcome{}, &Refusal{Step: p.Profile.Step, Reason: reason}
	}
	cmd := exec.Command(p.Command[0], p.Command[1:]...)
	cmd.Dir = p.Dir
	cmd.Env = append(os.Environ(), p.Env...)
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		return Outcome{Reason: reason}, fmt.Errorf("%s: %w", p.Profile.Step, err)
	}
	return Outcome{Reason: reason}, nil
}

// IsRefusal reports whether err is (or wraps) a Refusal.
func IsRefusal(err error) bool {
	var r *Refusal
	return errors.As(err, &r)
}

func dedupe(paths []string, tree string) []string {
	var out []string
	for _, p := range paths {
		p = filepath.Clean(p)
		if p == "" || (tree != "" && under(p, tree)) || contains(out, p) {
			continue
		}
		out = append(out, p)
	}
	return out
}

func under(p, root string) bool {
	rel, err := filepath.Rel(root, p)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, "../")
}

func underAny(p string, roots []string) bool {
	for _, r := range roots {
		if under(p, r) {
			return true
		}
	}
	return false
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}
