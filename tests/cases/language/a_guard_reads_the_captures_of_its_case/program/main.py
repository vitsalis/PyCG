
import ext
def f(): pass
def g(): pass
def h(): pass

def use(value):
    match value:
        case [handler, check] if check():
            handler()
use([f, g])
