"""Value types, and a union of them as icalendar's `prop/__init__.py` writes it."""
from typing import TypeAlias


class vAdr:
    def to_ical(self) -> bytes:
        return b"adr"


class vText:
    def to_ical(self) -> bytes:
        return b"text"

    def only_text(self) -> str:
        return "text"


class vUTCOffset(vText):
    pass


VPROPERTY: TypeAlias = vAdr | vText
