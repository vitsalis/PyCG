def func1():
    pass

def func2():
    pass

def func3():
    pass

handler = func1
for following in (func2, func3):
    handler()
    handler = following
