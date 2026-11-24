def func1():
    pass

def func2():
    pass

for f in frozenset([func1, func2]):
    f()
