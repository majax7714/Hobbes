"""A component whose `__getitem__` returns the union, as icalendar's does."""
from miniunion.prop import VPROPERTY, vAdr, vText


class Component(dict):
    def __getitem__(self, key) -> VPROPERTY:
        return super().__getitem__(key)

    def get_factory_for_property(self, name: str) -> VPROPERTY:
        return vText() if name == "SUMMARY" else vAdr()


class LazyStrategy:
    def is_lazy(self) -> bool:
        return True


class ParsedStrategy:
    def is_lazy(self) -> bool:
        return False


class Calendar(Component):
    _subcomponents: LazyStrategy | ParsedStrategy

    def __init__(self):
        super().__init__()
        self._subcomponents = ParsedStrategy()


def tzname(component: Component) -> bytes:
    return component["TZOFFSETFROM"].to_ical()


def render(utc_prop: VPROPERTY) -> bytes:
    return utc_prop.to_ical()


def parse(component: Component, name: str) -> bytes:
    factory = component.get_factory_for_property(name)
    return factory.to_ical()


def lazy(calendar: Calendar) -> bool:
    return calendar._subcomponents.is_lazy()


def only_one_holder(utc_prop: VPROPERTY) -> str:
    # Only vText declares `only_text`: one def in play, not a union member.
    return utc_prop.only_text()


def plain(value: vText) -> bytes:
    # Not a union: the call stands.
    return value.to_ical()
