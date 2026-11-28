
import ext
def f(): pass
def g(): pass
def h(): pass

class Modes:
    FAST = 1
class AlwaysEqual:
    def __eq__(self, other):
        return True
def use():
    match AlwaysEqual():
        case Modes.FAST:
            f()
