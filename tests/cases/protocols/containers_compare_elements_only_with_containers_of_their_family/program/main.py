
import collections
class Item:
    def __hash__(self): return 1
    def __eq__(self, other): return False
    def __lt__(self, other): return False
def compare0(a, b):
    try:
        [a] == (b,)
    except TypeError:
        pass
compare0(Item(), Item())
def compare1(a, b):
    try:
        collections.deque([a]) == [b]
    except TypeError:
        pass
compare1(Item(), Item())
def compare2(a, b):
    try:
        [[a]] == [(b,)]
    except TypeError:
        pass
compare2(Item(), Item())
def compare3(a, b):
    try:
        [a] < (b,)
    except TypeError:
        pass
compare3(Item(), Item())
def compare4(a, b):
    try:
        {1: a} < {1: b}
    except TypeError:
        pass
compare4(Item(), Item())
def compare5(a, b):
    try:
        [(a,)] == [(b,)]
    except TypeError:
        pass
compare5(Item(), Item())
def compare6(a, b):
    try:
        collections.deque([a]) == collections.deque([b])
    except TypeError:
        pass
compare6(Item(), Item())
def compare7(a, b):
    try:
        collections.deque([a]) < collections.deque([b])
    except TypeError:
        pass
compare7(Item(), Item())
def compare8(a, b):
    try:
        [(a,)] < [(b,)]
    except TypeError:
        pass
compare8(Item(), Item())
def compare9(a, b):
    try:
        [{1: a}] < [{1: b}]
    except TypeError:
        pass
compare9(Item(), Item())
def compare10(a, b):
    try:
        ({a},) < ({b},)
    except TypeError:
        pass
compare10(Item(), Item())
def compare11(a, b):
    try:
        {a} <= frozenset([b])
    except TypeError:
        pass
compare11(Item(), Item())
def compare12(a, b):
    try:
        {a: 1} == collections.OrderedDict([(b, 1)])
    except TypeError:
        pass
compare12(Item(), Item())
