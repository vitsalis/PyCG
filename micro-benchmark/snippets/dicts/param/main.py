def func2():
    pass

def func1(d):
    d["a"]()

d = {"a": func2}

func1(d)
