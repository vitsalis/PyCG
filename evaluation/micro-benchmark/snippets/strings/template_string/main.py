class Value:
    def __format__(self, spec):
        return "format"

def name():
    return "world"

template = t"{name()} {Value()}"
