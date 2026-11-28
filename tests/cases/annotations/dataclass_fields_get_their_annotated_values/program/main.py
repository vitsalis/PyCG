
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import dataclasses
from dataclasses import dataclass
from typing import NamedTuple
@dataclasses.dataclass
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
@dataclass(frozen=True)
class Frozen:
    strategy: "Strategy"
    def run(self):
        self.strategy(1)
class Pair(NamedTuple):
    first: Strategy
    def run(self):
        self.first(1)
class Plain:
    strategy: Strategy
    def run(self):
        self.strategy(1)
