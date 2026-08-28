//! See build.rs: `generated` exists iff the build script ran; `leaked`
//! exists iff it could read the planted secret.

#[cfg(canary_ran)]
pub fn generated() -> u8 {
    7
}

#[cfg(canary_leaked)]
pub fn leaked() -> u8 {
    13
}

pub fn plain() -> u8 {
    1
}
