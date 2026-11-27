
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import dataclasses
import sys
make = dataclasses.dataclass if sys.argv else dataclasses.dataclass(frozen=True)
@make
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
