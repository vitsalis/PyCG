def func2():
    pass

def func1():
    d = {"a": func2}
    return d

b = func1()
b["a"]()
