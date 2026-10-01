"""One test per function, so every ``with`` in core.py runs."""

from pywith.core import nested_call, plain, raising, through_contextlib, two


def test_plain():
    plain()


def test_raising():
    raising()


def test_two():
    two()


def test_nested_call():
    nested_call()


def test_through_contextlib():
    through_contextlib()
