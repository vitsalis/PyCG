
class Score:
    def __lt__(self, other): return True
    def __gt__(self, other): return True
    def __le__(self, other): return True
class Low:
    def __lt__(self, other): return True
class High:
    def __gt__(self, other): return True
def by_sorted():
    sorted([Score()])
def by_max():
    max([Score()])
def by_min(a, b):
    min(a, b)
def by_reflection():
    sorted([High()])
by_sorted()
by_max()
by_min(Low(), Low())
by_reflection()
