use std::fmt::Debug;

macro_rules! twice {
    ($x:expr) => {
        $x * 2
    };
}

pub fn compute(a: i64, b: i64) -> i64 {
    a + b
}

pub fn double_via_macro(x: i64) -> i64 {
    twice!(compute(x, 0))
}

pub struct Counter {
    count: i64,
}

impl Counter {
    pub fn new() -> Counter {
        Counter { count: 0 }
    }

    pub fn incr(&mut self) -> i64 {
        self.count += 1;
        self.count
    }
}

pub fn describe<T: Debug>(value: T) -> String {
    format!("{value:?}")
}
