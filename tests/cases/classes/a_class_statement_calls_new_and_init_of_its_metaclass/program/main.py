
class Meta(type):
    def __new__(mcs, name, bases, namespace, **options):
        namespace["hook"]()
        return super().__new__(mcs, name, bases, namespace)
    def __init__(cls, name, bases, namespace, **options):
        super().__init__(name, bases, namespace)
        cls.ready()
class Model(metaclass=Meta, flag=True):
    @staticmethod
    def hook(): pass
    @classmethod
    def ready(cls): pass
def declare():
    class Plain:
        pass
