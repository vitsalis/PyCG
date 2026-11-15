def load():
    pass

def save():
    pass

def reset():
    pass

def via_enumerate():
    for _, action in enumerate([load]):
        action()

def via_zip():
    for _, action in zip(["s"], [save]):
        action()

def via_reversed():
    for action in reversed([reset]):
        action()

via_enumerate()
via_zip()
via_reversed()
