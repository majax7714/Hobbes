"""opencode's id format (``schema/src/identifier.ts:9-32`` at v2.0.29).

``prefix`` + 12 hex chars (milliseconds * 4096 + a counter) + 14 base62
chars. Ascending ids sort by creation time; session ids use the inverted
("descending") value so newer sessions sort first.
"""

from __future__ import annotations

import secrets
import string
import time

_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase
_last = 0
_counter = 0


def _ident(descending: bool = False) -> str:
    global _last, _counter
    now = int(time.time() * 1000)
    _counter = _counter + 1 if now == _last else 1
    _last = now
    value = now * 0x1000 + _counter
    if descending:
        value = ~value & 0xFFFFFFFFFFFF
    stamp = "".join(f"{(value >> (40 - 8 * i)) & 0xFF:02x}" for i in range(6))
    return stamp + "".join(_ALPHABET[b % 62] for b in secrets.token_bytes(14))


def event_id() -> str:
    return "evt_" + _ident()


def message_id() -> str:
    return "msg_" + _ident()


def session_id() -> str:
    return "ses_" + _ident(descending=True)


def permission_id() -> str:
    return "per_" + _ident()


def form_id() -> str:
    return "frm_" + _ident()
