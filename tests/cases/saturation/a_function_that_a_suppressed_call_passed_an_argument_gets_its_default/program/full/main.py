def fallback(): pass
def real(): pass
def leaf(cb=fallback):
    cb()
def first(): return leaf
def second(): return leaf
def third(): return leaf
for factory in (first, second, third):
    factory()(real)
