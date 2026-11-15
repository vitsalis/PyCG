def func1():
    pass

def func2():
    pass

pairs = (("first", func1), ("second", func2))
table = {name: f for name, f in pairs}
table["second"]()
