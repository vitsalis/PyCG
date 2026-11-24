def func1():
    pass

def func2():
    pass

defaults = {"run": func1}
overrides = {"run": func2}
(defaults | overrides)["run"]()
