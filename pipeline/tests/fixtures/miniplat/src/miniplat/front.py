"""Callers that import what they call inside the function, as click's termui does."""


def raw_terminal():
    from .term import raw_terminal as f

    return f()


def get_pager_file():
    from .term import get_pager_file

    return get_pager_file()
