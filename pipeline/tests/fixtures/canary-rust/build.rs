//! The canary's build script — repo-authored code that lane B executes
//! (C-29). Three probes, each observable from the host side of the test:
//!
//! 1. `cargo:rustc-cfg=canary_ran` — proves the script executed at all,
//!    because `generated()` in lib.rs exists only under that cfg.
//! 2. a planted fake secret at a fixed host path: readable → the script
//!    emits `cargo:rustc-cfg=canary_leaked` and `leaked()` appears.
//! 3. a sentinel written outside the stage: present on the host afterwards
//!    → the script ran on the host.
use std::fs;

fn main() {
    println!("cargo:rustc-cfg=canary_ran");
    println!("cargo:rustc-check-cfg=cfg(canary_ran)");
    println!("cargo:rustc-check-cfg=cfg(canary_leaked)");
    if let Ok(secret) = fs::read_to_string("/tmp/hobbes-canary-secret") {
        if secret.contains("planted") {
            println!("cargo:rustc-cfg=canary_leaked");
        }
    }
    let _ = fs::write("/tmp/hobbes-canary-escaped", "the build script reached the host");
}
