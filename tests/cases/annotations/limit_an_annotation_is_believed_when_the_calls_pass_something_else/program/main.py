
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

def _helper(s: Strategy):
    s(1)
def use():
    _helper(Fast())
