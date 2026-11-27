def func1():
    pass

def func2():
    pass

config = {"on_start": func1, "on_stop": func2}
match config:
    case {"on_stop": handler}:
        handler()
