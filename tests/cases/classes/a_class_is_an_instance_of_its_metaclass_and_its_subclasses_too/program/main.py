
class Meta(type):
    def create(cls):
        return cls()
    def run(cls):
        cls.hook()
class Model(metaclass=Meta):
    def __init__(self): pass
    @staticmethod
    def hook(): pass
class Child(Model):
    def __init__(self): pass
