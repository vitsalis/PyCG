def greet():
    pass


class Hook:
    def __get__(self, obj, objtype=None):
        return greet


class App:
    hook = Hook()


App().hook()
