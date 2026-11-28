
def f(): pass
def g(): pass
def h(): pass

import ext
def some(command):
    handler = f
    match command:
        case "a":
            handler = g
        case "b":
            handler = h
    handler()
def every(command):
    handler = f
    match command:
        case "a":
            handler = g
        case _:
            handler = h
    handler()
