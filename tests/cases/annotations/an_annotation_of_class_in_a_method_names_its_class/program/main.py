
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

class Runner:
    def run(self): pass
    def copy(self):
        other: __class__ = make()
        other.run()
