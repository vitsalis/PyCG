
def trace(f):
    def wrapper():
        return f()
    return wrapper
@trace
def g(): pass
g()
