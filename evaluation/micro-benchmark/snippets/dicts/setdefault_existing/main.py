def func1():
    pass

def func2():
    pass

d = {"a": func1}
d.setdefault("a", func2)()
