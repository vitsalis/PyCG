
class Point:
    def __init__(self, x): pass
    def run(self): pass
def inner(): pass
def make(x):
    return inner
def use():
    for r in map(make, [1]):
        r()
    for p in map(Point, [1, 2]):
        p.run()
use()
