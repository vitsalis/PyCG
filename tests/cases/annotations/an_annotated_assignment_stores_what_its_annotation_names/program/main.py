
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import copy
import typing
class Runner:
    default: Strategy = None
    def __init__(self, given):
        self.strategy: Strategy = copy.copy(given)
        self.many: list[Strategy] = []
        self.table: dict[str, Strategy] = {}
        self.slots = {}
        self.slots["a"]: Strategy = None
    def attribute(self):
        self.strategy(1)
    def listed(self):
        for s in self.many:
            s(1)
    def mapped(self):
        self.table["x"](1)
    def subscript(self):
        self.slots["a"](1)
    def class_level(self):
        self.default(1)
def local(given):
    s: typing.Optional[Strategy] = copy.copy(given)
    s(1)
CURRENT: Strategy = None
def module_level():
    CURRENT(1)
