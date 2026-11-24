def func1():
    pass

def func2():
    pass

class Command:
    __match_args__ = ("action",)

    def __init__(self, action, fallback):
        self.action = action
        self.fallback = fallback

match Command(func1, func2):
    case Command(action, fallback=other):
        action()
