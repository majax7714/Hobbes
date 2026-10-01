"""A terminal reader written twice, once per platform, as click's is."""

import contextlib
import sys


def _translate(ch):
    return ch


if sys.platform == "win32":

    @contextlib.contextmanager
    def raw_terminal():
        yield -1

    def getchar():
        rv = "w"
        return _translate(rv)

else:

    @contextlib.contextmanager
    def raw_terminal():
        yield 0

    def getchar():
        with raw_terminal() as fd:
            return _translate(str(fd))


def describe():
    if sys.platform == "darwin":
        return _translate("mac")
    return "other"


def get_pager_file():
    return None
