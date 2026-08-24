package policy

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Locations of policy files relative to their scope root (ADR-001).
const (
	// RepoPolicyRel is the repo policy path relative to the repo root.
	RepoPolicyRel = ".hobbes/policies/repo.policy"
	// FolderPolicyRel is the folder policy path relative to any directory
	// inside the repo.
	FolderPolicyRel = ".hobbes/folder.policy"
)

// Chain is an ordered set of policy files, least specific first: box,
// repo, role, then folder policies from the repo root down to the working
// directory, then the derived agent policy. Resolve applies ADR-002
// semantics over this order.
type Chain struct {
	Files []*File
}

// RolePolicyRel is the directory, relative to the repo root, holding the
// standing per-role policies: <RolePolicyRel>/<role>.policy. A role policy
// is versioned with the repo and changes only by commit — it is the
// standing half of a session's policy (ADR-054).
const RolePolicyRel = ".hobbes/policies/roles"

// ChainOpts names the inputs of one policy chain (ADR-054).
//
// Two levels beyond the ADR-001 three: the **role** layer is the standing
// per-role policy, versioned with the repo and changed only by commits;
// the **agent** layer is the derived per-unit policy a change-spec emits
// (hobbes plan, ADR-051), loaded last and so most specific. ADR-002's
// deny-overrides-allow means a derived layer can narrow what the repo or
// role allows but can never widen past a repo or role deny — the
// guarantee that lets a generated file sit at the most specific level.
type ChainOpts struct {
	BoxPath     string // box policy; "" for none (ADR-003 rules)
	RepoRoot    string // the repo the command runs in
	Dir         string // the working directory, inside RepoRoot
	Role        string // session role; "" loads no role policy
	AgentPolicy string // derived agent policy path; "" for none
}

// builtinFloor is the engine's own box-level floor, prepended to every
// LoadChain result (ADR-011): Terraform state carries secrets and is denied
// unconditionally. Deny is unshadowable (ADR-002), so no repo or folder
// policy can override this, and there is deliberately no off switch.
func builtinFloor() *File {
	return &File{
		Version: 1,
		Rules: []Rule{{
			Pattern:  "*.tfstate*",
			Decision: Deny,
			Reason:   "tfstate carries secrets (built-in floor, ADR-011)",
		}},
		Source: "builtin:tfstate-floor",
		Level:  "box",
	}
}

// LoadChain assembles the policy chain for a command running in dir, which
// must be inside repoRoot (repoRoot itself is allowed). It is LoadChainFor
// with no role and no agent policy.
func LoadChain(boxPath, repoRoot, dir string) (*Chain, error) {
	return LoadChainFor(ChainOpts{BoxPath: boxPath, RepoRoot: repoRoot, Dir: dir})
}

// LoadChainFor assembles the policy chain described by opts, in the order
// builtin floor → box → repo → role → folder(s) → agent.
//
// BoxPath, if non-empty, must name an existing box policy — the caller
// decides whether a missing box policy is an error (an explicitly configured
// path) or skippable (the ~/.hobbes/box.policy default; see ADR-003). The
// repo policy, the role policy, and folder policies are loaded only where
// present: every directory from RepoRoot down to Dir contributes its
// folder.policy, deepest last, so deeper folders are more specific. The
// agent policy is different: it was explicitly asked for, so a missing
// file is an error rather than a skip — a session that silently ran
// without its derived policy would be running wider than it was planned.
//
// Any file whose declared scope disagrees with the level it is loaded at is
// an error.
//
// Every chain starts with the engine's built-in tfstate deny floor
// (ADR-011), before any configured box policy.
func LoadChainFor(opts ChainOpts) (*Chain, error) {
	chain := Chain{Files: []*File{builtinFloor()}}

	add := func(path, level string) error {
		f, err := LoadFile(path)
		if err != nil {
			return err
		}
		if f.Scope != "" && f.Scope != level {
			return fmt.Errorf("%s: declared scope %q but loaded as %s policy", path, f.Scope, level)
		}
		f.Level = level
		chain.Files = append(chain.Files, f)
		return nil
	}

	if opts.BoxPath != "" {
		if err := add(opts.BoxPath, "box"); err != nil {
			return nil, err
		}
	}

	repoRoot, err := filepath.Abs(opts.RepoRoot)
	if err != nil {
		return nil, err
	}
	dir, err := filepath.Abs(opts.Dir)
	if err != nil {
		return nil, err
	}
	rel, err := filepath.Rel(repoRoot, dir)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return nil, fmt.Errorf("directory %s is not inside repo %s", dir, repoRoot)
	}

	if p := filepath.Join(repoRoot, filepath.FromSlash(RepoPolicyRel)); fileExists(p) {
		if err := add(p, "repo"); err != nil {
			return nil, err
		}
	}

	if opts.Role != "" {
		p := filepath.Join(repoRoot, filepath.FromSlash(RolePolicyRel), opts.Role+".policy")
		if fileExists(p) {
			if err := add(p, "role"); err != nil {
				return nil, err
			}
		}
	}

	// Walk repoRoot → dir, collecting folder policies shallowest first.
	current := repoRoot
	parts := []string{}
	if rel != "." {
		parts = strings.Split(rel, string(filepath.Separator))
	}
	for i := 0; i <= len(parts); i++ {
		if i > 0 {
			current = filepath.Join(current, parts[i-1])
		}
		if p := filepath.Join(current, filepath.FromSlash(FolderPolicyRel)); fileExists(p) {
			if err := add(p, "folder"); err != nil {
				return nil, err
			}
		}
	}

	if opts.AgentPolicy != "" {
		if !fileExists(opts.AgentPolicy) {
			return nil, fmt.Errorf("agent policy %s does not exist (it was configured, so it is required)", opts.AgentPolicy)
		}
		if err := add(opts.AgentPolicy, "agent"); err != nil {
			return nil, err
		}
	}

	return &chain, nil
}

// fileExists reports whether path exists and is a regular file.
func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular()
}
