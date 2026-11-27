
import collections
class Key:
    def __hash__(self): return 0
    def __eq__(self, other): return False
    def __lt__(self, other): return False
sources = []
def copy():
    for source in sources:
        {*source, Key()}
def compare(a, b, outer):
    for inner in outer:
        [[a]] == [inner]
        collections.deque([a]) == inner
        sorted([[a], inner])
copy()
compare(Key(), Key(), LATE)
sources.extend([{Key()}, {Key(): 1}, [Key()]])
LATE = [(Key(),), [Key()], collections.deque([Key()])]
