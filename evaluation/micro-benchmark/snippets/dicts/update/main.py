def func1():
    pass

def func2():
    pass

d = {"a": func1}

d.update({"a": func2})
d["a"]()
