def record(name):
    pass


class Traced:
    def __getattribute__(self, name):
        record(name)
        return object.__getattribute__(self, name)

    def run(self):
        pass


Traced().run()
