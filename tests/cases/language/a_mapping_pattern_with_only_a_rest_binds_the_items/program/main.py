
import ext
def f(): pass
def g(): pass
def h(): pass

def use(value):
    match value:
        case {**rest}:
            rest["k"]()
use({"k": f})
