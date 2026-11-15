def func1():
    pass

def func2():
    pass

class Registry:
    def __init__(self):
        self.handlers = [func1, func2]

    def each(self):
        for h in self.handlers:
            yield h

registry = Registry()
for h in registry.each():
    h()
