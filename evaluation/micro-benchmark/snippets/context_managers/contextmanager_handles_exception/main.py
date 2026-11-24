from contextlib import contextmanager


def recover():
    pass


def fail():
    raise ValueError("bad")


def never():
    pass


@contextmanager
def guarded():
    try:
        yield
    except ValueError:
        recover()


with guarded():
    fail()
    never()
