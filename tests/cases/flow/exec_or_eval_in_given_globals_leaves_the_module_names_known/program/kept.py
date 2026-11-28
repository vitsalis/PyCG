def hit(): pass


def run(code):
    exec(code, None, {})


DEBUG = False


def trace():
    if DEBUG:
        hit()
