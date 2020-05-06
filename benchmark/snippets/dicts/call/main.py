def func1():
    pass

def func2():
    pass

d = {
    "a": func1,
    1: func2,
    2: 3
}

d["a"]()
d[1]()
