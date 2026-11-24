def func1():
    pass

def gen():
    yield func1

def consume(handlers):
    for h in handlers:
        h()

consume(gen())
