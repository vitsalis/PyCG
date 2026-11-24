def func1():
    pass

def func2():
    pass

def func3():
    pass

for f in (func1, func2, func3):
    if f is func2:
        continue
    f()
