class Plain:
    def __init__(self):
        pass


class Named:
    def __init__(self, name):
        pass


def make(kind):
    try:
        return kind()
    except TypeError:
        return None


for kind in (Plain, Named):
    make(kind)
