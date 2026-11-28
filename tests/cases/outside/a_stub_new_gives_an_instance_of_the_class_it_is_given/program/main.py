
class S(str):
    def __new__(cls, value):
        return super().__new__(cls, value)
    def go(self): pass
class E(Exception):
    def __new__(cls, *args):
        return super().__new__(cls, *args)
    def go(self): pass
class T(tuple):
    def __new__(cls, a, b):
        return tuple.__new__(cls, (a, b))
    def go(self): pass
S("x").go()
E().go()
T(1, 2).go()
str.__new__(str, "x").upper()
