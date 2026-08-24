// Package web serves the M7 human surface (architecture §7, ADR-022):
// one local HTTP server per repo exposing the derived knowledge layer as
// JSON and the built single-page app that renders it — Graph, Tests,
// Docs, Diff, and Sessions.
//
// Reads dominate: the extractor artifacts are passed through untouched
// (the pipeline owns their schema), and the server decodes only what it
// must compute over — narrative sources, for stale badges. The single
// mutating surface is escalation approve/deny, which delegates to
// internal/escalation so a verdict from the browser obeys exactly the
// rules a verdict from the CLI does.
//
// The server binds loopback only and rejects non-loopback Host headers:
// §7 puts remote access out of scope, and this surface can approve
// commands.
package web

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// Config is one server's fixed inputs.
type Config struct {
	// RepoRoot is the repo whose knowledge layer is served.
	RepoRoot string
	// LogDir is the session-state root (~/.hobbes/sessions) holding
	// flight logs and escalation queues, per ADR-015/016.
	LogDir string
}

// Server routes the API and the embedded app for one repo.
type Server struct {
	cfg Config
	mux *http.ServeMux
}

// New validates the config and builds the router. It touches the repo
// only to confirm it is a directory — artifacts are read per request, so
// an ingest that happens after startup is visible on the next reload
// (the ADR-017 fresh-read rule).
func New(cfg Config) (*Server, error) {
	if cfg.RepoRoot == "" {
		return nil, errors.New("repo root is required")
	}
	abs, err := filepath.Abs(cfg.RepoRoot)
	if err != nil {
		return nil, fmt.Errorf("repo root: %w", err)
	}
	info, err := os.Stat(abs)
	if err != nil {
		return nil, fmt.Errorf("repo root: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("repo root %s is not a directory", abs)
	}
	cfg.RepoRoot = abs

	s := &Server{cfg: cfg, mux: http.NewServeMux()}
	s.routes()
	return s, nil
}

// RepoRoot is the absolute repo path the server reads.
func (s *Server) RepoRoot() string { return s.cfg.RepoRoot }

func (s *Server) routes() {
	// Skeleton artifacts — byte passthrough (ADR-022).
	s.mux.HandleFunc("GET /api/overview", s.handleOverview)
	s.mux.HandleFunc("GET /api/graph", s.artifactHandler("graph.json"))
	s.mux.HandleFunc("GET /api/tests", s.artifactHandler("tests.json"))
	s.mux.HandleFunc("GET /api/interfaces", s.artifactHandler("interfaces.json"))

	// Narrative artifacts — decoded far enough to badge (ADR-019).
	s.mux.HandleFunc("GET /api/docs", s.handleDocsIndex)
	s.mux.HandleFunc("GET /api/docs/module/{id...}", s.handleModuleDoc)
	s.mux.HandleFunc("GET /api/docs/test/{id...}", s.handleTestDoc)
	s.mux.HandleFunc("GET /api/behaviors", s.handleBehaviors)
	s.mux.HandleFunc("GET /api/docs/invariants", s.handleInvariants)

	// Repo reads: provenance links and the line diff.
	s.mux.HandleFunc("GET /api/source", s.handleSource)
	s.mux.HandleFunc("GET /api/diff", s.handleDiff)
	s.mux.HandleFunc("GET /api/refs", s.handleRefs)

	// The two decision surfaces (ADR-026) — the only writes besides
	// escalation verdicts, and each one lands in a file a human reads.
	s.mux.HandleFunc("GET /api/intent", s.handleIntent)
	s.mux.HandleFunc("PUT /api/intent", s.handleWriteIntent)
	s.mux.HandleFunc("GET /api/decisions", s.handleDecisions)
	s.mux.HandleFunc("POST /api/decisions/{key}", s.handleVerdict)

	// Sessions: the flight recorder and the escalation queue.
	s.mux.HandleFunc("GET /api/sessions", s.handleSessions)
	s.mux.HandleFunc("GET /api/sessions/{id}/flight", s.handleFlight)
	s.mux.HandleFunc("GET /api/escalations", s.handleEscalations)
	s.mux.HandleFunc("POST /api/escalations/{id}/{verdict}", s.handleResolveEscalation)

	// An unmatched /api/ path is a 404 in JSON, never the app: without
	// this floor the SPA catch-all below answers 200 with HTML, so a
	// wrong method or a typo'd route reads as success.
	s.mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
		writeError(w, http.StatusNotFound, "no such endpoint: "+r.Method+" "+r.URL.Path, "")
	})

	// Everything else is the app. Registered without a method so it does
	// not conflict with the methodless /api/ floor above; appHandler
	// refuses anything but a read.
	s.mux.Handle("/", appHandler())
}

// Handler returns the routed server wrapped in the loopback guard.
func (s *Server) Handler() http.Handler { return loopbackOnly(s.mux) }

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.Handler().ServeHTTP(w, r)
}

// derivedPath is a path under the repo's derived artifact directory.
func (s *Server) derivedPath(rel ...string) string {
	parts := append([]string{s.cfg.RepoRoot, ".hobbes", "derived"}, rel...)
	return filepath.Join(parts...)
}

// --- transport helpers ------------------------------------------------------

// loopbackOnly rejects requests whose Host is not a loopback name. The
// bind address already restricts who can connect; this closes DNS
// rebinding, where a public name resolves to 127.0.0.1 and a remote page
// drives the surface (which can approve commands) through the browser.
func loopbackOnly(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !hostIsLoopback(r.Host) {
			http.Error(w, "hobbes-web serves loopback only (ADR-022)", http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// hostIsLoopback reports whether a Host header names this machine.
func hostIsLoopback(host string) bool {
	if host == "" {
		return false
	}
	name := host
	if h, _, err := net.SplitHostPort(host); err == nil {
		name = h
	}
	name = strings.Trim(name, "[]")
	if strings.EqualFold(name, "localhost") {
		return true
	}
	if ip := net.ParseIP(name); ip != nil {
		return ip.IsLoopback()
	}
	return false
}

// LoopbackAddr validates a bind address: loopback interfaces only, since
// the surface has no authentication and can resolve escalations.
func LoopbackAddr(addr string) error {
	host, port, err := net.SplitHostPort(addr)
	if err != nil {
		return fmt.Errorf("address %q: want host:port", addr)
	}
	if port == "" {
		return fmt.Errorf("address %q: missing port", addr)
	}
	if host == "" {
		return fmt.Errorf("address %q: empty host binds every interface; "+
			"hobbes-web serves loopback only (ADR-022)", addr)
	}
	if !hostIsLoopback(host) {
		return fmt.Errorf("address %q: hobbes-web serves loopback only (ADR-022); "+
			"put a tunnel in front if you need remote access", addr)
	}
	return nil
}

// apiError is the error body every failing endpoint returns: what went
// wrong and, where one exists, the command that fixes it.
type apiError struct {
	Error string `json:"error"`
	Hint  string `json:"hint,omitempty"`
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	buf, err := json.Marshal(body)
	if err != nil {
		http.Error(w, "encoding failed", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_, _ = w.Write(buf)
}

func writeError(w http.ResponseWriter, status int, msg, hint string) {
	writeJSON(w, status, apiError{Error: msg, Hint: hint})
}

// writeRawJSON passes an artifact through without decoding it (ADR-022).
func writeRawJSON(w http.ResponseWriter, body []byte) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	_, _ = w.Write(body)
}
