package web

import (
	"embed"
	"io/fs"
	"net/http"
	"strings"
)

// dist holds the built single-page app. The directory carries only a
// committed .gitkeep; `npm run build` in web/ writes the rest and the
// output is gitignored — the sandbox's static-proxy precedent (ADR-022).
// A clone that has never built still compiles and serves stubPage.
//
//go:embed all:dist
var dist embed.FS

// stubPage is what an unbuilt binary serves: the command that fixes it,
// not a blank 404.
const stubPage = `<!doctype html>
<meta charset="utf-8">
<title>hobbes-web — app not built</title>
<style>
 body{font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
      margin:0;display:grid;place-items:center;min-height:100vh;
      background:#14161a;color:#d6dae0}
 div{max-width:34rem;padding:2rem}
 code{background:#1e2229;padding:.15rem .4rem;border-radius:4px;color:#9fd3ff}
 h1{font-size:1.1rem;letter-spacing:.04em;text-transform:uppercase;color:#8b93a1}
</style>
<div>
 <h1>hobbes-web</h1>
 <p>The API is serving, but the web app has not been built into this binary.</p>
 <p>Build it, then rebuild the binary:</p>
 <p><code>cd web &amp;&amp; npm install &amp;&amp; npm run build</code><br>
    <code>cd go &amp;&amp; go build -o bin/hobbes-web ./cmd/hobbes-web</code></p>
 <p>For development, <code>npm run dev</code> proxies /api here.</p>
</div>
`

// appHandler serves the built app, falling back to index.html for any
// unknown path (client-side routing) and to stubPage when unbuilt. It is
// the mux's catch-all, so it also enforces that the app is read-only:
// the only writes this server accepts are the escalation verdicts.
func appHandler() http.Handler {
	sub, err := fs.Sub(dist, "dist")
	if err != nil {
		return readOnly(http.HandlerFunc(serveStub))
	}
	if _, err := fs.Stat(sub, "index.html"); err != nil {
		return readOnly(http.HandlerFunc(serveStub))
	}
	files := http.FileServer(http.FS(sub))
	return readOnly(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		clean := strings.TrimPrefix(r.URL.Path, "/")
		if clean == "" {
			clean = "index.html"
		}
		if _, err := fs.Stat(sub, clean); err != nil {
			// Unknown path: hand it to the app, which owns routing.
			r = r.Clone(r.Context())
			r.URL.Path = "/"
		}
		files.ServeHTTP(w, r)
	}))
}

// readOnly refuses any method that is not a read.
func readOnly(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// Built reports whether the app was compiled into this binary — the CLI
// says so at startup rather than leaving a stub page to explain it.
func Built() bool {
	sub, err := fs.Sub(dist, "dist")
	if err != nil {
		return false
	}
	_, err = fs.Stat(sub, "index.html")
	return err == nil
}

func serveStub(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if r.URL.Path != "/" {
		w.WriteHeader(http.StatusNotFound)
	}
	_, _ = w.Write([]byte(stubPage))
}
