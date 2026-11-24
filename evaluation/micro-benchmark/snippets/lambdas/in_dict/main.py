def func1():
    pass

def func2():
    pass

ops = {
    "first": lambda: func1(),
    "second": lambda: func2(),
}
ops["second"]()
