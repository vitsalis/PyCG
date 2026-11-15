def func1():
    pass

def run(handler):
    match handler:
        case f:
            f()

run(func1)
