class Cat:
    def __init__(self):
        pass


class Dog:
    def __init__(self):
        pass


def build(kind):
    return kind()


kind = Cat
build(kind)
kind = Dog
