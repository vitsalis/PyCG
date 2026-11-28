
class It:
    def __init__(self):
        self.done = False
    def __next__(self):
        if self.done:
            raise StopIteration
        self.done = True
        return self
It.__iter__ = It
xs = [It()]
for item in xs:
    xs.extend(item)
    break
