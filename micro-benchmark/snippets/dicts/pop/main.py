def func1():
    pass

def func2():
    pass

d = {"a": func1, "b": func2}
d.pop("a")()
