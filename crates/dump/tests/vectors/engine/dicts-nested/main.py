def func1():
    pass

def func2():
    pass

d = {
    "a": {
        "b": func1
    }
}

d["a"]["b"] = func2

d["a"]["b"]()
