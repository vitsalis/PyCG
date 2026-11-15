def greet(self):
    pass


def with_greeting(cls):
    cls.greet = greet
    return cls


@with_greeting
class Person:
    pass


Person().greet()
