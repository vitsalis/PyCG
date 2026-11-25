def func1():
    pass

def make(f):
    def inner():
        f()
    return inner

handler = make(func1)
handler()
