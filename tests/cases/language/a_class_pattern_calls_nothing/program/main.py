
import ext
def f(): pass
def g(): pass
def h(): pass

class Command:
    def __init__(self):
        pass
def use(value):
    match value:
        case Command():
            f()
