def func1():
    pass

def func2():
    pass

f = func1
[f for f in (func2,)]
f()
