def func1():
    pass

class Command:
    __match_args__ = ("action",)

    @property
    def action(self):
        return func1

match Command():
    case Command(handler):
        handler()
