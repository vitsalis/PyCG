class Factory:
    pass


def make(cls):
    return cls


classmethod(make).__get__(Factory(), **{})()
