def read(self):
    return 1


class Plain:
    pass


thing = Plain()
try:
    property.__init__(thing, read)
except TypeError:
    pass
try:
    thing.fget(thing)
except AttributeError:
    pass
