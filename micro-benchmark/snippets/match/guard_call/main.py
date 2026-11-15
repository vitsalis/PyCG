def func1():
    pass

def fallback():
    pass

def accepts(f):
    return f is not func1

def choose(handler):
    match handler:
        case f if accepts(f):
            return f
        case _:
            return fallback

choose(func1)()
