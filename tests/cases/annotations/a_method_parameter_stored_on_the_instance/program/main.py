
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

class Retrying:
    def __init__(self, stop: Strategy = None):
        self.stop = stop
    def iter(self):
        self.stop(1)
