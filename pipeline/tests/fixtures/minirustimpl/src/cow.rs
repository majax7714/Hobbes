#[cfg(feature = "alloc")]
#[derive(Clone, Debug)]
pub enum Imp<'a> {
    Borrowed(&'a [u8]),
}

#[cfg(not(feature = "alloc"))]
#[derive(Clone, Debug)]
pub struct Imp<'a>(&'a [u8]);

#[cfg(feature = "alloc")]
pub fn width(bytes: &[u8]) -> usize {
    bytes.len()
}

#[cfg(not(feature = "alloc"))]
pub fn width(bytes: &[u8]) -> usize {
    count(bytes)
}

fn count(bytes: &[u8]) -> usize {
    bytes.len()
}
