from contextlib import contextmanager


def acquire():
    pass


def release():
    pass


@contextmanager
def managed():
    acquire()
    try:
        yield "resource"
    finally:
        release()


with managed() as resource:
    pass
