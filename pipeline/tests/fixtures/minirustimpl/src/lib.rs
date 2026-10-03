mod client;
mod cow;
mod ext;

use client::{Client, Describe, Id};
use ext::Pointer;

pub fn span(start: *mut u8, end: *mut u8) -> usize {
    unsafe { end.distance(start) }
}

pub fn offset(start: *const u8, end: *const u8) -> usize {
    unsafe { end.distance(start) }
}

pub fn make(name: &str) -> String {
    let client = Client::new(name);
    let id: Id = Id::from(name);
    let _ = id;
    client.describe() + &Describe::describe(&client)
}

pub fn measure(bytes: &[u8]) -> usize {
    cow::width(bytes)
}
