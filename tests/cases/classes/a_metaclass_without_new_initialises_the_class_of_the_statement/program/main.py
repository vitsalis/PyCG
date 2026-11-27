
class Meta(type):
    def __init__(cls, name, bases, namespace):
        cls.ready()
class First(metaclass=Meta):
    @classmethod
    def ready(cls): pass
def declare():
    class Second(First):
        @classmethod
        def ready(cls): pass
