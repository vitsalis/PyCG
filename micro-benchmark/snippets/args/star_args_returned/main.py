class Base:
    def __new__(cls, *args):
        return args[0]


class Plugin(Base):
    pass


class Hook(Base):
    pass


class Left:
    def run(self):
        pass


class Right:
    def run(self):
        pass


def first(*args):
    return args[0]


def func1():
    pass


def func2():
    pass


a = first(func1)
b = first(func2)
a()
Plugin(Left()).run()
Hook(Right())
