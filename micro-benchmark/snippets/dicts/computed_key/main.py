def func1():
    pass

def func2():
    pass

d = {"ab": func1, "a": func2}
prefix = "a"
d[prefix + "b"]()
