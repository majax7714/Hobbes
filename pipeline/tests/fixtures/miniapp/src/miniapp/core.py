"""Core domain logic."""

import os

from miniapp import util

MODE = os.getenv("MINIAPP_MODE")


class Engine:
    def __init__(self, limit):
        self.limit = limit

    def run(self, item):
        self.check(item)
        return util.normalize(item)

    def check(self, item):
        if len(item) > self.limit:
            raise ValueError(item)


def top_level(item):
    engine = Engine(10)
    return engine.run(item)
