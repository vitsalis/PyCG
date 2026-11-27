def good(): pass
def other(): pass
TABLE = {'a': good, 'b': other}
def pick(key):
    TABLE[key]()
def first(): return pick
def second(): return pick
def third(): return pick
for factory in (first, second, third):
    factory()('a')
