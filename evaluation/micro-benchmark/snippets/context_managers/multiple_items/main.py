class Lock:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Timer:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


with Lock("a") as lock, Timer() as timer:
    pass
