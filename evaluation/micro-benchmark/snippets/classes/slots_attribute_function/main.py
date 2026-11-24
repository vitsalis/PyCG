def on_ready():
    pass


class Task:
    __slots__ = ("callback",)

    def __init__(self, callback):
        self.callback = callback

    def finish(self):
        self.callback()


Task(on_ready).finish()
