
def f(): pass
class Number:
    def __add__(self, other):
        return self
    def __radd__(self, other):
        return f
    def __iadd__(self, other):
        return self
    def __neg__(self):
        return self
    def __lt__(self, other):
        return True
    def __gt__(self, other):
        return True
    def __eq__(self, other):
        return True
    def run(self): pass

def use(a, b):
    (a + b).run()
    (1 + a)()
    -a
use(Number(), Number())
