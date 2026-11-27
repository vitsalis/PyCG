def func1():
    pass

def make():
    return func1

def run(f=make()):
    f()

run()
