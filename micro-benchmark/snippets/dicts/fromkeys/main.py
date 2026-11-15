def func1():
    pass

d = dict.fromkeys(["a", "b"], func1)
d["b"]()
