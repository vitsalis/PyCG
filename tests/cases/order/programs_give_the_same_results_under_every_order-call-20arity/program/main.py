
class Needs:
    def __init__(self, value): pass
    def __call__(self, event): pass
class Empty:
    def __init__(self): pass
def one(a): pass
def keyword(*, key): pass
def late():
    return [Needs, Empty, one, keyword]
def run(kind, f):
    kind()(1)
    f(key=1)
    f(1)
for kind in late():
    run(kind, kind)
