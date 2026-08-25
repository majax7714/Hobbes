//! The Rust MIR resolution oracle (ADR-089, design §7; D-O6).
//!
//! A `RUSTC_WRAPPER`: cargo invokes it as `mir-oracle <rustc> <args…>`.
//! For a workspace crate (`CARGO_PRIMARY_PACKAGE` set) it runs the real
//! compiler in-process through `rustc_driver` and, after analysis, walks
//! every body's MIR: each `Call` terminator is one site, resolved with
//! `Instance::try_resolve` — the compiler's own answer, after
//! monomorphisation where the caller is monomorphic. Every other crate
//! (dependencies, build scripts, `rustc -vV`) is passed straight to rustc.
//!
//! Grain (the harness README, D-O4): the site is the line of the call's
//! `fn_span` — the callee expression without receiver and dot, i.e. the
//! callee name's line; a call that came out of a macro is attributed to
//! the invocation site (`source_callsite`). A target is the declaration's
//! identifier line (`def_ident_span`); generic instantiations collapse to
//! the origin `DefId` by construction; closures are identified by their
//! declaration span and marked. "External" is by *file*, not by crate —
//! `mylib::f` called from the same repo's bin crate is in-repo.
//!
//! Modes: `static` when the instance resolved to an item or closure;
//! `macro` when that static call sits in the expansion of a bang macro
//! the repo does not define (the author wrote the invocation, not the
//! call; the miss class names it);
//! `dynamic` for a `dyn Trait` call (`InstanceKind::Virtual`), a call
//! through a generic bound that the caller's own generics leave
//! unresolved (`try_resolve` → `Ok(None)`), or a function pointer. The
//! dynamic site carries the trait method as `interface` when there is
//! one, so a Hobbes edge to the trait method grades *abstract*, not
//! contradicted. Macro *invocations* are not calls to the compiler and
//! never appear; the Hobbes side drops edges to `macro` symbols before
//! grading and counts them.
//!
//! Output: one JSON file per rustc invocation in `HOBBES_ORACLE_OUT`,
//! merged by `oracle rust-mir` into the lane's `OracleExport`.

#![feature(rustc_private)]

extern crate rustc_driver;
extern crate rustc_hir;
extern crate rustc_interface;
extern crate rustc_middle;
extern crate rustc_session;
extern crate rustc_span;

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::process::Command;

use rustc_driver::{Callbacks, Compilation};
use rustc_hir::def::DefKind;
use rustc_hir::def_id::DefId;
use rustc_interface::interface::Compiler;
use rustc_middle::mir::TerminatorKind;
use rustc_middle::ty::{self, Instance, InstanceKind, TyCtxt, TypingEnv};
use rustc_span::hygiene::{DesugaringKind, ExpnKind, MacroKind};
use rustc_span::Span;

struct Oracle {
    repo: PathBuf,
    out: PathBuf,
    crate_label: String,
    /// Sites in code the compiler generated — the test harness, attribute
    /// and derive macro output — which no source line calls from; dropped
    /// and counted, never graded against Hobbes.
    generated: usize,
}

#[derive(Clone)]
struct Target {
    path: Option<String>,
    line: usize,
    name: String,
    kind: &'static str,
    external: bool,
    closure: bool,
}

struct Site {
    path: String,
    line: usize,
    col: usize,
    caller: String,
    mode: &'static str,
    interface: Option<Target>,
    targets: Vec<Target>,
}

impl Callbacks for Oracle {
    fn after_analysis<'tcx>(&mut self, _compiler: &Compiler, tcx: TyCtxt<'tcx>) -> Compilation {
        let mut sites: BTreeMap<(String, usize, usize), Site> = BTreeMap::new();
        for local in tcx.hir_body_owners() {
            let def_id = local.to_def_id();
            match tcx.def_kind(def_id) {
                DefKind::Fn | DefKind::AssocFn | DefKind::Closure | DefKind::Const { .. }
                | DefKind::AssocConst { .. } | DefKind::Static { .. } | DefKind::AnonConst => {}
                _ => continue,
            }
            if tcx.is_constructor(def_id) {
                continue;
            }
            let body = tcx.instance_mir(InstanceKind::Item(def_id));
            let typing_env = TypingEnv::post_analysis(tcx, def_id);
            let caller = tcx.def_path_str(def_id);
            for bb in body.basic_blocks.iter() {
                let Some(term) = &bb.terminator else { continue };
                let TerminatorKind::Call { func, fn_span, .. } = &term.kind else { continue };
                if generated(*fn_span) {
                    self.generated += 1;
                    continue;
                }
                let site_span = callsite(*fn_span);
                let Some((path, line, col)) = self.local_pos(tcx, site_span) else { continue };
                let fty = func.ty(&body.local_decls, tcx);
                let (mut mode, interface, targets) = match fty.kind() {
                    ty::FnDef(callee, args) => self.resolve(tcx, typing_env, *callee, args.skip_binder()),
                    ty::FnPtr(..) => ("dynamic", None, vec![]),
                    ty::Closure(callee, _) => ("static", None, vec![self.target(tcx, *callee)]),
                    _ => ("dynamic", None, vec![]),
                };
                if mode == "static" && self.foreign_macro(tcx, *fn_span) {
                    // The call is in the body of a macro the repo does not
                    // define (criterion_group!, tokio::main's block): the
                    // author wrote the invocation, not the call.
                    mode = "macro";
                }
                let key = (path.clone(), line, col);
                let site = sites.entry(key).or_insert_with(|| Site {
                    path, line, col, caller: caller.clone(), mode, interface: interface.clone(), targets: vec![],
                });
                for t in targets {
                    if !site.targets.iter().any(|s| s.path == t.path && s.line == t.line && s.name == t.name) {
                        site.targets.push(t);
                    }
                }
            }
        }
        let mut files: Vec<String> = tcx
            .sess
            .source_map()
            .files()
            .iter()
            .filter_map(|f| self.rel_path(f.name.clone().into_local_path()?.as_path()))
            .collect();
        files.sort();
        files.dedup();
        self.write(tcx, &sites, &files);
        Compilation::Continue
    }
}

fn callsite(span: Span) -> Span {
    if span.from_expansion() { span.source_callsite() } else { span }
}

/// True when the call was written by the compiler, not the author: the
/// test harness (`AstPass`), an attribute macro (`#[test]`'s wrapper
/// closure), a derive, or the `.await` desugaring (H-16). A bang macro's
/// body is the author's code and attributes to its invocation site
/// instead.
fn generated(span: Span) -> bool {
    let mut ctxt = span.ctxt();
    loop {
        let data = ctxt.outer_expn_data();
        match data.kind {
            ExpnKind::Root => return false,
            ExpnKind::AstPass(_) => return true,
            ExpnKind::Macro(MacroKind::Attr | MacroKind::Derive, _) => return true,
            // `.await` desugars to a poll loop whose callee is the async
            // fn's body (a coroutine): the authored call is the one to the
            // async fn itself, which MIR also carries at the same site.
            ExpnKind::Desugaring(DesugaringKind::Await) => return true,
            ExpnKind::Macro(MacroKind::Bang, _) | ExpnKind::Desugaring(_) => {}
        }
        let parent = data.call_site.ctxt();
        if parent == ctxt {
            return false;
        }
        ctxt = parent;
    }
}

impl Oracle {
    fn rel_path(&self, p: &Path) -> Option<String> {
        let abs = if p.is_absolute() { p.to_path_buf() } else { std::env::current_dir().ok()?.join(p) };
        let abs = abs.canonicalize().unwrap_or(abs);
        let rel = abs.strip_prefix(&self.repo).ok()?;
        let s = rel.to_string_lossy().replace('\\', "/");
        if s.split('/').any(|part| part == "target" || part == ".git") {
            return None;
        }
        Some(s)
    }

    fn local_pos(&self, tcx: TyCtxt<'_>, span: Span) -> Option<(String, usize, usize)> {
        let loc = tcx.sess.source_map().lookup_char_pos(span.lo());
        let path = loc.file.name.clone().into_local_path()?;
        let rel = self.rel_path(&path)?;
        Some((rel, loc.line, loc.col_display + 1))
    }

    /// True when the call sits in the expansion of a bang macro whose
    /// definition is outside the repo.
    fn foreign_macro(&self, tcx: TyCtxt<'_>, span: Span) -> bool {
        let mut ctxt = span.ctxt();
        loop {
            let data = ctxt.outer_expn_data();
            match data.kind {
                ExpnKind::Root => return false,
                ExpnKind::Macro(MacroKind::Bang, _) => {
                    let local = data
                        .macro_def_id
                        .and_then(|d| self.local_pos(tcx, tcx.def_span(d)))
                        .is_some();
                    if !local {
                        return true;
                    }
                }
                _ => {}
            }
            let parent = data.call_site.ctxt();
            if parent == ctxt {
                return false;
            }
            ctxt = parent;
        }
    }

    fn target(&self, tcx: TyCtxt<'_>, def_id: DefId) -> Target {
        let ident = tcx.def_ident_span(def_id);
        let span = ident.unwrap_or_else(|| tcx.def_span(def_id));
        let name = tcx.def_path_str(def_id);
        let closure = tcx.is_closure_like(def_id);
        let kind = if closure {
            "closure"
        } else if span.from_expansion() {
            // A declaration a macro wrote (criterion_group!'s `benches`):
            // no source identifier, so no Hobbes symbol can exist for it.
            "generated"
        } else if tcx.def_kind(def_id) == DefKind::AssocFn {
            "method"
        } else {
            "function"
        };
        match self.local_pos(tcx, span) {
            Some((path, line, _)) => Target { path: Some(path), line, name, kind, external: false, closure },
            None => Target { path: None, line: 0, name, kind, external: true, closure },
        }
    }

    fn resolve<'tcx>(
        &self,
        tcx: TyCtxt<'tcx>,
        typing_env: TypingEnv<'tcx>,
        callee: DefId,
        args: ty::GenericArgsRef<'tcx>,
    ) -> (&'static str, Option<Target>, Vec<Target>) {
        let trait_method = tcx.trait_of_assoc(callee).map(|_| self.target(tcx, callee));
        match Instance::try_resolve(tcx, typing_env, callee, args) {
            Ok(Some(inst)) => match inst.def {
                InstanceKind::Virtual(def, _) => ("dynamic", Some(self.target(tcx, def)), vec![]),
                InstanceKind::Item(def) => {
                    let mut t = self.target(tcx, def);
                    if tcx.is_closure_like(def) {
                        t.closure = true;
                    }
                    ("static", None, vec![t])
                }
                // Shims (reify, clone, drop glue, closure-once) carry the
                // source item they were made for as their def_id.
                other => ("static", None, vec![self.target(tcx, other.def_id())]),
            },
            // The caller's own generics leave the bound unresolved: the
            // trait method is all the compiler can say here.
            Ok(None) => ("dynamic", trait_method, vec![]),
            Err(_) => ("dynamic", trait_method, vec![]),
        }
    }

    fn write(&self, tcx: TyCtxt<'_>, sites: &BTreeMap<(String, usize, usize), Site>, files: &[String]) {
        let mut s = String::new();
        s.push_str("{\n");
        let _ = writeln!(s, "  \"crate\": {},", json_str(&self.crate_label));
        let _ = writeln!(s, "  \"rustc\": {},", json_str(&format!("rustc {}", tcx.sess.cfg_version)));
        let _ = writeln!(s, "  \"generated_sites\": {},", self.generated);
        s.push_str("  \"files\": [");
        for (i, f) in files.iter().enumerate() {
            if i > 0 { s.push_str(", "); }
            s.push_str(&json_str(f));
        }
        s.push_str("],\n  \"sites\": [\n");
        for (i, site) in sites.values().enumerate() {
            if i > 0 { s.push_str(",\n"); }
            let _ = write!(
                s,
                "    {{\"pos\": {{\"path\": {}, \"line\": {}}}, \"col\": {}, \"caller\": {}, \"mode\": \"{}\"",
                json_str(&site.path), site.line, site.col, json_str(&site.caller), site.mode
            );
            if let Some(iface) = &site.interface {
                let _ = write!(s, ", \"interface\": {}", target_json(iface));
            }
            s.push_str(", \"targets\": [");
            for (j, t) in site.targets.iter().enumerate() {
                if j > 0 { s.push_str(", "); }
                s.push_str(&target_json(t));
            }
            s.push_str("]}");
        }
        s.push_str("\n  ]\n}\n");
        let _ = std::fs::create_dir_all(&self.out);
        let file = self.out.join(format!("{}.json", sanitize(&self.crate_label)));
        if let Err(e) = std::fs::write(&file, s) {
            eprintln!("mir-oracle: cannot write {}: {e}", file.display());
        }
    }
}

fn target_json(t: &Target) -> String {
    let mut s = String::from("{");
    if let Some(p) = &t.path {
        let _ = write!(s, "\"pos\": {{\"path\": {}, \"line\": {}}}, ", json_str(p), t.line);
    } else {
        s.push_str("\"pos\": {\"path\": \"\", \"line\": 0}, ");
    }
    let _ = write!(s, "\"name\": {}, \"kind\": \"{}\"", json_str(&t.name), t.kind);
    if t.external { s.push_str(", \"external\": true"); }
    if t.closure { s.push_str(", \"closure\": true"); }
    s.push('}');
    s
}

fn json_str(v: &str) -> String {
    let mut s = String::from("\"");
    for c in v.chars() {
        match c {
            '"' => s.push_str("\\\""),
            '\\' => s.push_str("\\\\"),
            '\n' => s.push_str("\\n"),
            '\t' => s.push_str("\\t"),
            c if (c as u32) < 0x20 => { let _ = write!(s, "\\u{:04x}", c as u32); }
            c => s.push(c),
        }
    }
    s.push('"');
    s
}

fn sanitize(s: &str) -> String {
    s.chars().map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '_' }).collect()
}

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    let mut it = args.iter();
    while let Some(a) = it.next() {
        if a == flag {
            return it.next().cloned();
        }
        if let Some(v) = a.strip_prefix(&format!("{flag}=")) {
            return Some(v.to_string());
        }
    }
    None
}

fn main() {
    let mut args: Vec<String> = std::env::args().collect();
    // As a RUSTC_WRAPPER: argv[1] is the rustc path, the rest its arguments.
    let rustc = if args.len() > 1 { args.remove(1) } else { "rustc".to_string() };
    let rustc_args: Vec<String> = args.into_iter().skip(1).collect();
    let primary = std::env::var_os("CARGO_PRIMARY_PACKAGE").is_some();
    let out = std::env::var_os("HOBBES_ORACLE_OUT").map(PathBuf::from);
    let repo = std::env::var_os("HOBBES_ORACLE_REPO").map(PathBuf::from);
    let is_compile = rustc_args.iter().any(|a| a == "--crate-name");
    if !(primary && is_compile) || out.is_none() || repo.is_none() {
        let status = Command::new(&rustc).args(&rustc_args).status().expect("mir-oracle: cannot exec rustc");
        std::process::exit(status.code().unwrap_or(1));
    }
    let crate_name = arg_value(&rustc_args, "--crate-name").unwrap_or_default();
    let crate_type = arg_value(&rustc_args, "--crate-type").unwrap_or_else(|| "bin".into());
    let test = rustc_args.iter().any(|a| a == "--test");
    let meta = arg_value(&rustc_args, "-C")
        .filter(|v| v.starts_with("metadata="))
        .map(|v| v[9..].to_string())
        .unwrap_or_default();
    let target_name = std::env::var("CARGO_BIN_NAME").ok().unwrap_or_default();
    let label = format!(
        "{crate_name}{}{}{}{}",
        if target_name.is_empty() { String::new() } else { format!(" bin={target_name}") },
        if crate_type == "bin" { String::new() } else { format!(" {crate_type}") },
        if test { " (test)" } else { "" },
        if meta.is_empty() { String::new() } else { format!(" #{}", &meta[..meta.len().min(8)]) },
    );
    let repo = repo.unwrap();
    let repo = repo.canonicalize().unwrap_or(repo);
    let mut cb = Oracle { repo, out: out.unwrap(), crate_label: label, generated: 0 };
    let mut at_args = vec![rustc];
    at_args.extend(rustc_args);
    rustc_driver::run_compiler(&at_args, &mut cb);
}
