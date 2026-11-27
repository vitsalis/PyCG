
def f(): pass
def g(): pass
def h(): pass

import ext
command = "stop"
match command:
    case "go":
        f()
    case "stop" | "halt":
        g()
    case _:
        h()
match command:
    case [first, *rest]:
        f()
    case None:
        f()
    case word if ext.check(word):
        h()
