
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

def keep(cls):
    return cls
@keep
class Config:
    strategy: Strategy
    def run(self):
        self.strategy(1)
