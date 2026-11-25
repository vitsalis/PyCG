class Registry:
    def __init__(self):
        self.items = []

    def add(self, func):
        self.items.append(func)
        return func


registry = Registry()


@registry.add
def task():
    pass


for item in registry.items:
    item()
