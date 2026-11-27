
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

def combine(*strategies: Strategy):
    for s in strategies:
        s(1)
def named(**strategies: Strategy):
    for s in strategies.values():
        s(1)
