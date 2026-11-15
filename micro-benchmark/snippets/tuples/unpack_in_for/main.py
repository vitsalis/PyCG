def func1():
    pass

def func2():
    pass

for name, f in (("first", func1), ("second", func2)):
    f()
