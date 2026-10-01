"""A Windows-only module, as click's _winconsole is."""

import sys

assert sys.platform == "win32"


def _write(text):
    return text


def write_console(text):
    return _write(text)
