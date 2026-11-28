
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import dataclasses
@dataclasses.dataclass
class Config:
    strategy: Strategy
def use():
    config = Config(Fast())
    config.strategy(1)
