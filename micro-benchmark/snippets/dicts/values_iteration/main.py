def func1():
    pass

def func2():
    pass

d = {"a": func1, "b": func2}
for f in d.values():
    f()
