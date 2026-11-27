
import ext
def f(): pass
def g(): pass
def h(): pass

class Command:
    __match_args__ = ("action",)
    def __init__(self, action, fallback):
        self.action = action
        self.fallback = fallback
class Lazy:
    __match_args__ = ("action",)
    @property
    def action(self):
        return h
class Sub(Command):
    pass
def positional():
    match Command(f, g):
        case Command(action, fallback=other):
            action()
def keyword():
    match Command(f, g):
        case Command(fallback=other):
            other()
def inherited():
    match Sub(f, g):
        case Sub(action):
            action()
def computed():
    match Lazy():
        case Lazy(action):
            action()
def builtin(value):
    match value:
        case str(text):
            text.upper()
builtin("name")
