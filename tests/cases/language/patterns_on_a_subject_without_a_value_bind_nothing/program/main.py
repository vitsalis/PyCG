
import ext
def f(): pass
def g(): pass
def h(): pass

class C:
    __match_args__ = ("a",)
def use():
    n = None
    match n.attr:
        case 1.5:
            f()
        case {**rest}:
            rest.get("k")
        case [a]:
            g()
        case [*r]:
            h()
        case C(a=y):
            y()
        case C(z):
            z()
