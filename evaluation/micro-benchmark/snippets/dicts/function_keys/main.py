def func1():
    pass

def func2():
    pass

d = {func1: "first", func2: "second"}
for f in d.keys():
    f()
