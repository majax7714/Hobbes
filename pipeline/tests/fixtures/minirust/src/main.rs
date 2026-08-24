use minilib::compute;

mod helpers;
mod sub;

#[path = "./deep/extra.rs"]
mod extra;

fn main() {
    helpers::greet();
    sub::from_sub();
    extra::extra_fn();
    println!("{}", compute(1, 2));
}

pub fn double(x: i64) -> i64 {
    x * 2
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_double() {
        assert_eq!(double(2), 4);
    }
}
