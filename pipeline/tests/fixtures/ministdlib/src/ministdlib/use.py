"""Each call is rooted at a standard-library import (ADR-164, C-181)."""
import email.utils as eu
import importlib.metadata
import json
import sys
from functools import reduce
from gettext import gettext as _
from urllib import parse
from urllib.parse import urlsplit

from ministdlib import helpers

try:
    from urllib.parse import quote
except ImportError:
    from ministdlib.helpers import urlsplit as quote


def run(url):
    urlsplit(url)
    parse.urlsplit(url)
    eu.formatdate(1)
    importlib.metadata.version("x")
    sys.exit(1)
    _("text")
    quote(url)
    reduce(max, [1])
    json.dumps(1)
    sys.stdout.write("x")
    helpers.urlsplit(url)


def shadowed(parse):
    parse.urlsplit("x")
