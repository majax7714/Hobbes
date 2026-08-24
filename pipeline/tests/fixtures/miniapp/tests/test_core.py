"""Tests for miniapp.core."""

from miniapp import util
from miniapp.core import top_level


def helper(x):
    return util.normalize(x)


def test_top_level():
    assert top_level("abc") == "abc"


class TestEngine:
    def test_run(self):
        assert helper("ABC") == "abc"
