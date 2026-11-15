from collections.abc import Iterator

def first():
    pass

class Countdown(Iterator):
    def __init__(self):
        self.left = 1

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return first

for handler in Countdown():
    handler()
