
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

class Other:
    def __call__(self, state): pass
def run():
    s: Strategy = Other()
    s(1)
