use minilib::{compute, Counter};

#[test]
fn integration_works() {
    assert_eq!(compute(2, 3), 5);
    let mut c = Counter::new();
    assert_eq!(c.incr(), 1);
}
