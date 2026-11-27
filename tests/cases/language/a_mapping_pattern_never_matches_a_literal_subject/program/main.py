
import ext
def f(): pass
def g(): pass
def h(): pass

def use():
    match 1:
        case {"a": x}:
            f()
        case _:
            g()
