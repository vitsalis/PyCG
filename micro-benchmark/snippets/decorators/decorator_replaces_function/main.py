def noop():
    pass


def disabled(func):
    return noop


@disabled
def expensive():
    pass


expensive()
