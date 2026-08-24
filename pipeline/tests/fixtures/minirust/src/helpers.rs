pub fn greet() -> String {
    let mode = std::env::var("MINIRUST_MODE").unwrap_or_default();
    format!("hello {mode}")
}
