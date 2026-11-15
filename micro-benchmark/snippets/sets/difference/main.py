def func1():
    pass

def func2():
    pass

for f in {func1, func2} - {func2}:
    f()
