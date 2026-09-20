"""One test per function, so every line of core.py runs."""

from pygen.core import apply, double, firsts, squares, total


def test_double():
    assert double(3) == 6


def test_total():
    assert total([1, 2, 3]) == 12


def test_firsts():
    assert firsts([1, 2]) == (1, 2)


def test_squares():
    assert squares([1, 2]) == [2, 4]


def test_apply():
    assert apply([1, 2]) == [2, 4]
