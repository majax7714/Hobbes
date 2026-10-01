"""The names core.py uses inside its later defs."""


class Abort(Exception):
    """Raised to stop a command."""


class Usage(Exception):
    """Raised on a bad invocation."""


class Payload:
    """A value a command carries."""
