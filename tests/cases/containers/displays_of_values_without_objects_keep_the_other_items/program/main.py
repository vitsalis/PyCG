def f(): pass
def g(): pass
def h(): pass

def value(): return 1
None[f()]
s = {*None, value()}
l = [*None, value()]
d = {**None, "k": value()}
