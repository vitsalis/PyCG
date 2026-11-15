from contextlib import ContextDecorator


def start():
    pass


def stop():
    pass


class Tracked(ContextDecorator):
    def __enter__(self):
        start()
        return self

    def __exit__(self, *exc):
        stop()
        return False


@Tracked()
def work():
    pass


work()
