def log_error():
    pass


def fail():
    raise ValueError("bad")


def never():
    pass


class Suppress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        log_error()
        return True


with Suppress():
    fail()
    never()
