def func1():
    pass

class Modes:
    FAST = 1

class AlwaysEqual:
    def __eq__(self, other):
        return True

match AlwaysEqual():
    case Modes.FAST:
        func1()
