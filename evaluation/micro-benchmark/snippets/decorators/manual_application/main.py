def shout(func):
    def wrapper():
        return func()

    return wrapper


def hello():
    pass


hello = shout(hello)
hello()
