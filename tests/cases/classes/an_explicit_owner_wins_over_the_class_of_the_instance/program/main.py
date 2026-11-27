
class Base:
    @staticmethod
    def kind(): pass
class Other:
    @staticmethod
    def kind(): pass
def make(cls):
    cls.kind()
classmethod(make).__get__(Base(), Other)()
