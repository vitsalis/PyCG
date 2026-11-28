
import ext
def f(): pass
def g(): pass
def h(): pass

def known():
    match (f, g, h):
        case [first, *rest]:
            rest[0]()
def positions(value):
    match value:
        case [first, _, last]:
            first()
            last()
def ends():
    match [f, g, h]:
        case [*_, before, last]:
            before()
positions([f, ext.middle, h])
