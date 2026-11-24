class Factory:
    pass


def make(cls):
    return cls


def helper():
    pass


method = classmethod(make)
static = staticmethod(helper)
for attempt in (
    lambda: method.__get__(None),
    lambda: method.__get__(None, None),
    lambda: static.__get__(None),
    lambda: method.__get__(Factory(), owner=Factory),
    lambda: static.__get__(Factory(), Factory, 1),
):
    try:
        attempt()()
    except TypeError:
        pass
