class CountCalls:
    def __init__(self, func):
        self.func = func
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        return self.func(*args)


@CountCalls
def greet(name):
    pass


greet("a")
