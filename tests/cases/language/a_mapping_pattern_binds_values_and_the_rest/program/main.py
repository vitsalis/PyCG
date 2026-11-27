
import ext
def f(): pass
def g(): pass
def h(): pass

def values(config):
    match config:
        case {"on_stop": handler}:
            handler()
def rest():
    config = {"on_start": f, "on_stop": g}
    match config:
        case {"on_start": handler, **others}:
            others["on_stop"]()
values({"on_start": h, "on_stop": f})
