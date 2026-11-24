def func1():
    pass

def func2():
    pass

d = dict(first=func1, second=func2)
d["second"]()
