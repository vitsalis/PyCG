
UNSET = object()
def first_set(first, second):
    return second if first is UNSET else first
def either(a, b):
    return a or b
def fallback(a):
    return a if a else make()
def make():
    return g
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def use():
    first_set(UNSET, f)()
    either(h, None)()
    fallback(None)()
first_set(k, UNSET)
either(k, None)
