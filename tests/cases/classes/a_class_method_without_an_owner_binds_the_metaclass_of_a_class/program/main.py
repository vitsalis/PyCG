
class Meta(type):
    @staticmethod
    def kind(): pass
class Model(metaclass=Meta):
    @staticmethod
    def kind(): pass
def make(cls):
    cls.kind()
classmethod(make).__get__(Model)()
