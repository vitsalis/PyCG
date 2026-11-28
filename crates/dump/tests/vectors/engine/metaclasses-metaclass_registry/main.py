registry = {}


class Registered(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        registry[name] = cls


class Base(metaclass=Registered):
    def run(self):
        pass


class Alpha(Base):
    def run(self):
        pass


class Beta(Base):
    def run(self):
        pass


registry["Alpha"]().run()
