
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

class Holder:
    str = Fast
    def use(self, text: str):
        text.upper()
        text(1)
