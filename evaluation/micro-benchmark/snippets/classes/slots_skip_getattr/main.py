def work():
    pass


def fallback():
    pass


class Lazy:
    __slots__ = ("action",)

    def __init__(self, action):
        self.action = action

    def __getattr__(self, name):
        return fallback

    def run(self):
        self.action()


Lazy(work).run()
