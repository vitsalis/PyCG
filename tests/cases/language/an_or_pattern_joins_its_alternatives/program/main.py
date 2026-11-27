
import ext
def f(): pass
def g(): pass
def h(): pass

def unknown(value):
    match value:
        case [handler] | [_, handler]:
            handler()
unknown([f, g])
