
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

s: Strategy
def run(given):
    t: Strategy
    t = given
    t(1)
class Plain:
    strategy: Strategy
    def __init__(self, given):
        self.strategy = given
    def run(self):
        self.strategy(1)
def module_level():
    s(1)
