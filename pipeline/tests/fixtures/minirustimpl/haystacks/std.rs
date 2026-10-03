// ADR-165's residual (C-182): memchr keeps a copy of the standard library
// under benchmarks/haystacks as search input, which no crate compiles, and
// it repeats names freely. This file is not a module of any target.
pub struct B;

pub fn helper() -> u8 {
    1
}

pub fn render() -> u8 {
    helper()
}

pub const B: u8 = helper();

pub fn render() -> u8 {
    helper() + 1
}
