def func1():
    pass

def func2():
    pass

[last := f for f in (func1, func2)]
last()
