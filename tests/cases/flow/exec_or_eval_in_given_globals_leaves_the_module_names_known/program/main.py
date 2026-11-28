import kept
def depr(major, minor, cause, fix): pass
def hit(): pass


def run(code, expression):
    env = {}
    exec(code, env)
    eval(expression, globals=env)


def serve():
    depr(0, 13, "cause")
    hit()


DEBUG = False


def trace():
    if DEBUG:
        hit()
